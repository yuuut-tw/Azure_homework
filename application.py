import os
import json
from imgur_python import Imgur
from datetime import datetime, timezone, timedelta
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import (
    MessageEvent,
    TextMessage,
    TextSendMessage,
    FlexSendMessage,
    ImageMessage)

from azure.cognitiveservices.vision.computervision import ComputerVisionClient
from azure.cognitiveservices.vision.computervision.models import OperationStatusCodes
from azure.cognitiveservices.vision.face import FaceClient
from msrest.authentication import CognitiveServicesCredentials


app = Flask(__name__)

# Configuration
# ===============================================================

# LineChat Bot
LINE_SECRET = os.getenv('LINE_SECRET')
LINE_TOKEN = os.getenv('LINE_TOKEN')
LINE_BOT = LineBotApi(LINE_TOKEN)
HANDLER = WebhookHandler(LINE_SECRET)

# Computer vision
CV_KEY = os.getenv("CV_KEY")
CV_END = os.getenv("CV_END")
CV_CLIENT = ComputerVisionClient(
    CV_END, CognitiveServicesCredentials(CV_KEY)
)

# Face Recognition
FACE_KEY = os.getenv("FACE_KEY")
FACE_END = os.getenv("FACE_END")
FACE_CLIENT = FaceClient(FACE_END, CognitiveServicesCredentials(FACE_KEY))
PERSON_GROUP_ID = "tibame"

# Imgur
IMGUR_CONFIG = {
  "client_id": os.getenv("IMGUR_ID"),
  "client_secret": os.getenv("IMGUR_SECRET"),
  "access_token": os.getenv("IMGUR_ACCESS_TOKEN"),
  "refresh_token": os.getenv("IMGUR_REFRESH_TOKEN")
}

IMGUR_CLIENT = Imgur(config=IMGUR_CONFIG)


# APP content
# ===============================================================

@app.route("/")
def hello():
    "hello world"
    return "Hello World!!!!!"


@app.route("/callback", methods=["POST"])
def callback():
    # X-Line-Signature: 數位簽章
    signature = request.headers["X-Line-Signature"]
    print(signature)
    body = request.get_data(as_text=True)
    print(body)
    try:
        HANDLER.handle(body, signature)
    except InvalidSignatureError:
        print("Check the channel secret/access token.")
        abort(400)
    return "OK"


# message 可以針對收到的訊息種類
@HANDLER.add(MessageEvent, message=TextMessage)
def handle_message(event):

    json_dict = {
      "YOUTUBE": "YOUTUBE.json",
      "GOSSIP": "GOSSIP.json"}

    message = event.message.text.upper()

    # If message is the key of json_dict, then load the json file and show on the chat.
    try:
        json_file = json_dict[message]
        with open(f"templates/{json_file}", "r") as f_r:
            bubble = json.load(f_r)
        # f_r.close()
        LINE_BOT.reply_message(event.reply_token,
                               [FlexSendMessage(alt_text="Report", contents=bubble)])

    except:
        message = TextSendMessage(text=event.message.text)
        LINE_BOT.reply_message(event.reply_token, message)

# azure 功能
# ================================================================


# 定義人臉辨識函數
def azure_face_recognition(filename):
    PERSON_GROUP_ID = "cfb101"
    FACE_CLIENT = FaceClient(FACE_END, CognitiveServicesCredentials(FACE_KEY))
    img = open(filename, "r+b")  # read binary
    detected_face = FACE_CLIENT.face.detect_with_stream(img,
                                                        detection_model="detection_01")
    # 多於一張臉的情況
    if len(detected_face) != 1:
        return ""
    results = FACE_CLIENT.face.identify([detected_face[0].face_id],
                                        PERSON_GROUP_ID)
    # 沒有結果的情況
    if len(results) == 0:
        return "unknown"
    result = results[0].as_dict()

    # 找不到相像的人
    if len(result["candidates"]) == 0:
        return "unknown"
    # 雖然有類似的人，但信心程度太低
    if result["candidates"][0]["confidence"] < 0.5:
        return "unknown"

    person = FACE_CLIENT.person_group_person.get(PERSON_GROUP_ID,
                                                 result["candidates"][0]["person_id"])

    return person.name


@HANDLER.add(MessageEvent, message=ImageMessage) # 檢查輸入是否為image
def handle_content_message(event):

    filename = "{}.jpg".format(event.message.id)
    message_content = LINE_BOT.get_message_content(event.message.id)
    with open(filename, "wb") as f_w:
        for chunk in message_content.iter_content():
            f_w.write(chunk)
    f_w.close()
    image = IMGUR_CLIENT.image_upload(filename, "first", "first")
    #link = image["response"]["data"]["link"]
    name = azure_face_recognition(filename)

    if name != "":
        now = datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M")
        output = "{0}, {1}".format(name, now)
    else:
        output = "unknown"
        output = TextSendMessage(text=output)

    LINE_BOT.reply_message(event.reply_token,
                           output)