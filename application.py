import os
import re
import time
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
from PIL import Image, ImageDraw, ImageFont
from azure.cognitiveservices.vision.computervision import ComputerVisionClient
from azure.cognitiveservices.vision.computervision.models import OperationStatusCodes
from azure.cognitiveservices.vision.face import FaceClient
from msrest.authentication import CognitiveServicesCredentials

app = Flask(__name__)

### Configuration
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

### APP 功能(文字、圖片)
# ===============================================================

# hello test (new adjustment)
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


# Line Bot for 文字訊息
# ===============================================================

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


# Azure 圖片辨識
# ===============================================================

# 定義各項功能(人臉辨識、光學辨識、物件描述、物件偵測)
# 人臉辨識函數
def azure_face_recognition(filename):
    PERSON_GROUP_ID = "cfb101"
    FACE_CLIENT = FaceClient(FACE_END, CognitiveServicesCredentials(FACE_KEY))
    img = open(filename, "r+b")
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

# 光學OCR函數(for車牌)
def azure_ocr(url):
    """
    Azure OCR: get characters from image url
    """
    ocr_results = CV_CLIENT.read(url, raw=True)
    # Get the operation location (URL with an ID at the end) from the response
    operation_location_remote = ocr_results.headers["Operation-Location"]
    # Grab the ID from the URL
    operation_id = operation_location_remote.split("/")[-1]
    # Call the "GET" API and wait for it to retrieve the results
    while True:
        get_handw_text_results = CV_CLIENT.get_read_result(operation_id)
        if get_handw_text_results.status not in ["notStarted", "running"]:
            break
        time.sleep(1)

    # Get detected text
    text = []
    if get_handw_text_results.status == OperationStatusCodes.succeeded:
        for text_result in get_handw_text_results.analyze_result.read_results:
            for line in text_result.lines:
                if len(line.text) <= 8:
                    text.append(line.text)

    # 車牌辨識 & 發票辨識
    r_plate = re.compile("[0-9A-Z]{2,4}[.-]{1}[0-9A-Z]{2,4}")
    r_invoice = re.compile("[A-Z]{2}[-][1-9]{8}")
    matched_plate = list(filter(r_plate.match, text))
    matched_invoice = list(filter(r_invoice.match, text))
    if len(matched_plate) > 0:
        text = matched_plate
    elif len(matched_invoice) > 0:
        text = matched_invoice
    else:
        text = []

    return text[0].replace(".", "-") if len(text) > 0 else ""

# 物件描述函數
def azure_describe(url):
    """
    Output azure image description result
    """
    description_results = CV_CLIENT.describe_image(url)
    output = ""
    for caption in description_results.captions:
        output += "'{}' with confidence {:.2f}% \n".format(
            caption.text, caption.confidence * 100
        )
    return output

# 物件偵測函數
def azure_object_detection(url, filename):
    img = Image.open(filename)
    draw = ImageDraw.Draw(img)
    font_size = int(5e-2 * img.size[1])
    fnt = ImageFont.truetype("static/TaipeiSansTCBeta-Regular.ttf", size=font_size)
    object_detection = CV_CLIENT.detect_objects(url)
    if len(object_detection.objects) > 0:
        for obj in object_detection.objects:
            left = obj.rectangle.x
            top = obj.rectangle.y
            right = obj.rectangle.x + obj.rectangle.w
            bot = obj.rectangle.y + obj.rectangle.h
            name = obj.object_property
            confidence = obj.confidence
            print("{} at location {}, {}, {}, {}".format(name, left, right, top, bot))
            draw.rectangle([left, top, right, bot], outline=(255, 0, 0), width=3)
            draw.text(
                [left, top + font_size],
                "{} {}".format(name, confidence),
                fill=(255, 0, 0),
                font=fnt,
            )
    img.save(filename)
    image = IMGUR_CLIENT.image_upload(filename, "", "")
    link = image["response"]["data"]["link"]
    os.remove(filename)
    return link

# LineBot For 圖片訊息
@HANDLER.add(MessageEvent, message=ImageMessage)
def handle_content_message(event):

    filename = "{}.jpg".format(event.message.id)
    message_content = LINE_BOT.get_message_content(event.message.id)
    with open(filename, "wb") as f_w:
        for chunk in message_content.iter_content():
            f_w.write(chunk)
    f_w.close()
    image = IMGUR_CLIENT.image_upload(filename, "first", "first")
    link = image["response"]["data"]["link"]
    # 人臉
    name = azure_face_recognition(filename)
    # 車牌
    plate = azure_ocr(link)
    # 物件偵測
    link_ob = azure_object_detection(link, filename)

    if name != "":
        now = datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M")
        output = "{0}, {1}".format(name, now)

    elif len(plate) > 0:
        output = "License Plate: {}".format(plate)
        link = link_ob
    elif link_ob != "":
        output = azure_describe(link)
        link = link_ob
    else:
        output = "unknown"

    with open("templates/azure_output.json", "r") as f_r:
        bubble = json.load(f_r)
    f_r.close()
    bubble["hero"]["url"] = link
    bubble["body"]["contents"][0]["text"] = output

    LINE_BOT.reply_message(
        event.reply_token, [FlexSendMessage(alt_text="Detected Result ", contents=bubble)]
    )
