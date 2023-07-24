import math
import requests
import json
import time
import sys
from io import BytesIO
from http import HTTPStatus
from websocket import create_connection # type: ignore
from websocket._exceptions import WebSocketConnectionClosedException # type: ignore
from PIL import Image

from loguru import logger
from bs4 import BeautifulSoup

from src.mappings import ColorMapper
from src import utils

class PlaceClient:
    def __init__(self, config_path):
        self.logger = logger

        # Data
        self.json_data = utils.get_json_data(self, config_path)
        logger.debug("{}", self.json_data)
        self.pixel_x_start: int = self.json_data["image_start_coords"][0]
        self.pixel_y_start: int = self.json_data["image_start_coords"][1]

        self.rgb_colors_array = ColorMapper.generate_rgb_colors_array()

        self.access_token = None
        self.access_token_expiry_timestamp = None

         # Image information
        self.pix = None
        self.image_size = None
        self.image_path = self.json_data.get("image_path", "images/image.png")


    def set_pixel_and_check_ratelimit(
        self,
        access_token,
        pixel_x_start,
        pixel_y_start,
        name,
        color_index_in=18,
        canvas_index=0,
    ):
        # canvas structure:
        # 0 | 1 | 2
        # 3 | 4 | 5
        logger.warning(
            "Attempting to place {} pixel at {}, {}",
            ColorMapper.color_id_to_name(color_index_in),
            pixel_x_start + (1000 * (canvas_index % 3)),
            pixel_y_start + (1000 * (canvas_index // 3)),
        )

        url = "https://gql-realtime-2.reddit.com/query"

        payload = json.dumps(
            {
                "operationName": "setPixel",
                "variables": {
                    "input": {
                        "actionName": "r/replace:set_pixel",
                        "PixelMessageData": {
                            "coordinate": {"x": pixel_x_start, "y": pixel_y_start},
                            "colorIndex": color_index_in,
                            "canvasIndex": canvas_index,
                        },
                    }
                },
                "query": "mutation setPixel($input: ActInput!) {\n  act(input: $input) {\n    data {\n      ... on BasicMessage {\n        id\n        data {\n          ... on GetUserCooldownResponseMessageData {\n            nextAvailablePixelTimestamp\n            __typename\n          }\n          ... on SetPixelResponseMessageData {\n            timestamp\n            __typename\n          }\n          __typename\n        }\n        __typename\n      }\n      __typename\n    }\n    __typename\n  }\n}\n",
            }
        )
        headers = {
            "origin": "https://garlic-bread.reddit.com",
            "referer": "https://garlic-bread.reddit.com/",
            "apollographql-client-name": "mona-lisa",
            "Authorization": "Bearer " + access_token,
            "Content-Type": "application/json",
        }
        response = requests.post(
            url,
            headers=headers,
            data=payload,
        )
        logger.debug(
            "Received response: {}", response.text
        )

        # There are 2 different JSON keys for responses to get the next timestamp.
        # If we don't get data, it means we've been rate limited.
        # If we do, a pixel has been successfully placed.
        if response.json()["data"] is None:
            logger.debug(response.json().get("errors"))
            waitTime = math.floor(
                response.json()["errors"][0]["extensions"]["nextAvailablePixelTs"]
            )
            logger.error(
                "Failed placing pixel: rate limited",
            )
        else:
            waitTime = math.floor(
                response.json()["data"]["act"]["data"][0]["data"][
                    "nextAvailablePixelTimestamp"
                ]
            )
            logger.success(
                "Succeeded placing pixel at {}, {}",
                (pixel_x_start + (1000 * (canvas_index % 3))-1500), (pixel_y_start + (1000 * (canvas_index // 3))-1000)
            )

        # Reddit returns time in ms and we need seconds, so divide by 1000
        return waitTime / 1000

    def get_board(self, access_token):
        logger.debug("Connecting and obtaining board images")
        while True:
            try:
                ws = create_connection(
                    "wss://gql-realtime-2.reddit.com/query",
                    origin="https://garlic-bread.reddit.com",
                )
                break
            except Exception:
                logger.error(
                    "Failed to connect to websocket, trying again in 30 seconds..."
                )
                time.sleep(30)

        ws.send(
            json.dumps(
                {
                    "type": "connection_init",
                    "payload": {"Authorization": "Bearer " + access_token},
                }
            )
        )
        while True:
            try:
                msg = ws.recv()
            except WebSocketConnectionClosedException as e:
                logger.error(e)
                continue
            if msg is None:
                logger.error("Reddit failed to acknowledge connection_init")
                exit()
            if msg.startswith('{"type":"connection_ack"}'):
                logger.debug("Connected to WebSocket server")
                break
        logger.debug("Obtaining Canvas information")
        ws.send(
            json.dumps(
                {
                    "id": "1",
                    "type": "start",
                    "payload": {
                        "variables": {
                            "input": {
                                "channel": {
                                    "teamOwner": "GARLICBREAD",
                                    "category": "CONFIG",
                                }
                            }
                        },
                        "extensions": {},
                        "operationName": "configuration",
                        "query": "subscription configuration($input: SubscribeInput!) {\n  subscribe(input: $input) {\n    id\n    ... on BasicMessage {\n      data {\n        __typename\n        ... on ConfigurationMessageData {\n          colorPalette {\n            colors {\n              hex\n              index\n              __typename\n            }\n            __typename\n          }\n          canvasConfigurations {\n            index\n            dx\n            dy\n            __typename\n          }\n          canvasWidth\n          canvasHeight\n          __typename\n        }\n      }\n      __typename\n    }\n    __typename\n  }\n}\n",
                    },
                }
            )
        )

        while True:
            canvas_payload = json.loads(ws.recv())
            if canvas_payload["type"] == "data":
                canvas_details = canvas_payload["payload"]["data"]["subscribe"]["data"]
                logger.debug("Canvas config: {}", canvas_payload)
                break

        canvas_sockets = []

        canvas_count = len(canvas_details["canvasConfigurations"])

        for i in range(0, canvas_count):
            canvas_sockets.append(2 + i)
            logger.debug("Creating canvas socket {}", canvas_sockets[i])

            ws.send(
                json.dumps(
                    {
                        "id": str(2 + i),
                        "type": "start",
                        "payload": {
                            "variables": {
                                "input": {
                                    "channel": {
                                        "teamOwner": "GARLICBREAD",
                                        "category": "CANVAS",
                                        "tag": str(i),
                                    }
                                }
                            },
                            "extensions": {},
                            "operationName": "replace",
                            "query": "subscription replace($input: SubscribeInput!) {\n  subscribe(input: $input) {\n    id\n    ... on BasicMessage {\n      data {\n        __typename\n        ... on FullFrameMessageData {\n          __typename\n          name\n          timestamp\n        }\n        ... on DiffFrameMessageData {\n          __typename\n          name\n          currentTimestamp\n          previousTimestamp\n        }\n      }\n      __typename\n    }\n    __typename\n  }\n}\n",
                        },
                    }
                )
            )

        imgs = []
        logger.debug("A total of {} canvas sockets opened", len(canvas_sockets))

        while len(canvas_sockets) > 0:
            temp = json.loads(ws.recv())
            logger.debug("Waiting for WebSocket message")

            if temp["type"] == "data":
                logger.debug("Received WebSocket data type message")
                msg = temp["payload"]["data"]["subscribe"]

                if msg["data"]["__typename"] == "FullFrameMessageData":
                    logger.debug("Received full frame message")
                    img_id = int(temp["id"])
                    logger.debug("Image ID: {}", img_id)

                    if img_id in canvas_sockets:
                        logger.debug("Getting image: {}", msg["data"]["name"])
                        imgs.append(
                            [
                                img_id,
                                Image.open(
                                    BytesIO(
                                        requests.get(
                                            msg["data"]["name"],
                                            stream=True,
                                        ).content
                                    )
                                ),
                            ]
                        )
                        canvas_sockets.remove(img_id)
                        logger.debug(
                            "Canvas sockets remaining: {}", len(canvas_sockets)
                        )

        for i in range(0, canvas_count - 1):
            ws.send(json.dumps({"id": str(2 + i), "type": "stop"}))

        ws.close()

        new_img_width = (
            max(map(lambda x: x["dx"], canvas_details["canvasConfigurations"]))
            + canvas_details["canvasWidth"]
        )
        logger.debug("New image width: {}", new_img_width)

        new_img_height = (
            max(map(lambda x: x["dy"], canvas_details["canvasConfigurations"]))
            + canvas_details["canvasHeight"]
        )
        logger.debug("New image height: {}", new_img_height)

        new_img = Image.new("RGB", (new_img_width, new_img_height))

        for idx, img in enumerate(sorted(imgs, key=lambda x: x[0])):
            logger.debug("Adding image (ID {}): {}", img[0], img[1])
            dx_offset = int(canvas_details["canvasConfigurations"][idx]["dx"])
            dy_offset = int(canvas_details["canvasConfigurations"][idx]["dy"])
            new_img.paste(img[1], (dx_offset, dy_offset))

        return new_img

    def get_unset_pixel(self):
        originalX = x = 0
        originalY = y = 0
        loopedOnce = False
        imgOutdated = True

        while True:
            if x >= self.image_size[0]:
                y += 1
                x = 0

            if y >= self.image_size[1]:
                y = 0

            if x == originalX and y == originalY and loopedOnce:
                logger.info(
                    "All pixels correct, trying again in 10 seconds... ",
                )
                time.sleep(10)
                imgOutdated = True

            if imgOutdated:
                boarding = self.get_board(self.access_token)
                pix2 = boarding.convert("RGB").load()
                imgOutdated = False

            logger.debug("{}, {}", x + self.pixel_x_start, y + self.pixel_y_start)
            logger.debug(
                "{}, {}, boarding, {}, {}", x, y, self.image_size[0], self.image_size[1]
            )

            target_rgb = self.pix[x, y]

            new_rgb = ColorMapper.closest_color(
                target_rgb, self.rgb_colors_array, self.legacy_transparency
            )

            if pix2[x + self.pixel_x_start, y + self.pixel_y_start] != new_rgb:
                logger.debug(
                    "{}, {}, {}, {}",
                    pix2[x + self.pixel_x_start, y + self.pixel_y_start],
                    new_rgb,
                    new_rgb != (69, 42, 0),
                    pix2[x, y] != new_rgb,
                )

                # (69, 42, 0) is a special color reserved for transparency.
                if new_rgb != (69, 42, 0):
                    logger.debug(
                        "Replacing {} pixel at: {},{} with {} color",
                        pix2[x + self.pixel_x_start, y + self.pixel_y_start],
                        x + self.pixel_x_start,
                        y + self.pixel_y_start,
                        new_rgb,
                    )
                    break
                else:
                    logger.info(
                        "Transparent Pixel at {}, {} skipped",
                        x + self.pixel_x_start,
                        y + self.pixel_y_start,
                    )
            x += 1
            loopedOnce = True
        return x, y, new_rgb


    def task(self, name, passw):
        self.name = name
        self.passw = passw
        repeat_forever = True
        while True:
            # Timing shit
            pixel_place_frequency = 315 # + random.random()*60

            current_time = math.floor(time.time())
            next_placement_time = current_time + pixel_place_frequency

            while True:
                current_timestamp = math.floor(time.time())
                if self.access_token_expiry_timestamp is None or current_timestamp >= self.access_token_expiry_timestamp:
                    logger.info(
                        "User {}: Refreshing access token", name
                    )
                    try:
                        username = name
                        password = passw
                    except Exception:
                        logger.exception(
                            "You need to provide all required fields to worker '{}'",
                            name,
                        )
                        continue
                    while True:
                        try:
                            client = requests.Session()

                            client.headers.update(
                                {
                                        "User-Agent": f"{utils.select_user_agent(self)}",
                                        "Origin": "https://www.reddit.com/",
                                        "Sec-Fetch-Dest": "empty",
                                        "Sec-Fetch-Mode": "cors",
                                        "Sec-Fetch-Site": "same-origin"
                                    }
                                )

                            r = client.get(
                                "https://www.reddit.com/login",
                            )
                            login_get_soup = BeautifulSoup(r.content, "html.parser")
                            csrf_token = login_get_soup.find(
                                "input", {"name": "csrf_token"}
                            )["value"]
                            data = {
                                "username": username,
                                "password": password,
                                "dest": "https://new.reddit.com/",
                                "csrf_token": csrf_token,
                            }

                            r = client.post(
                                "https://www.reddit.com/login",
                                data=data,
                            )
                            break
                        except Exception as e:
                            logger.error(e)
                            logger.error(
                                "Failed to connect to websocket, trying again in 30 seconds..."
                            )
                            time.sleep(30)
                    if r.status_code != HTTPStatus.OK.value:
                        # password is probably invalid
                        logger.exception("{} - Authorization failed!", username)
                        logger.debug("response: {} - {}", r.status_code, r.text)
                        return
                    else:
                        logger.success("{} - Authorization successful!", username)
                    logger.info("Obtaining access token...")
                    r = client.get(
                        "https://new.reddit.com/",
                    )
                    data_str = (
                        BeautifulSoup(r.content, features="html.parser")
                        .find("script", {"id": "data"})
                        .contents[0][len("window.__r = ") : -1]
                    )
                    data = json.loads(data_str)
                    response_data = data["user"]["session"]

                    if "error" in response_data:
                        logger.info(
                            "An error occured. Make sure you have the correct credentials. Response data: {}",
                            response_data,
                        )
                        exit()

                    self.access_token = response_data["accessToken"]
                    access_token_expires_in_seconds = response_data[
                        "expiresIn"
                    ]  # this is usually "3600"

                    self.access_token_expiry_timestamp = current_timestamp + int(access_token_expires_in_seconds)
                    logger.info(
                        "Received new access token: {}************",
                        self.access_token,
                    )

                if self.access_token is not None and (
                    current_timestamp >= next_placement_time
                ):
                    current_x, current_y, new_rgb = self.get_unset_pixel() 
                    new_rgb_hex = ColorMapper.rgb_to_hex(new_rgb)
                    pixel_color_index = ColorMapper.COLOR_MAP[new_rgb_hex]
                        
                    canvas = 0
                    pixel_x_start = self.pixel_x_start + current_x
                    pixel_y_start = self.pixel_y_start + current_y
                    while pixel_x_start > 999:
                        pixel_x_start -= 1000
                        canvas += 1
                    while pixel_y_start > 999:
                        pixel_y_start -= 1000
                        canvas += 3

                    # draw the pixel onto r/place
                    next_placement_time = self.set_pixel_and_check_ratelimit(
                        self.access_token,
                        pixel_x_start,
                        pixel_y_start,
                        name,
                        pixel_color_index,
                        canvas,
                    )

                time_until_next_draw = next_placement_time - current_timestamp

                # If next_pixel_placement_time (returned by place_pixel_and_check_ratelimit)
                # is too large, user is likely permabanned
                if time_until_next_draw > 10000:
                    logger.warning(
                        "CANCELLED :: Rate-Limit Banned"
                    )   
                    repeat_forever = False
                    break


            if not repeat_forever:
                break 



def main():
    client = PlaceClient('config.json')
    user = input("give username")
    passw = input("give password")
    client.task(user, passw)
        
if __name__ == "__main__":
    main()
