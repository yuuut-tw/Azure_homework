import os
import json
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import (
    MessageEvent,
    TextMessage,
    TextSendMessage,
    FlexSendMessage)


app = Flask(__name__)

LINE_SECRET = os.getenv('LINE_SECRET')
LINE_TOKEN = os.getenv('LINE_TOKEN')
LINE_BOT = LineBotApi(LINE_TOKEN)
HANDLER = WebhookHandler(LINE_SECRET)


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


    # 將要發出去的文字變成TextSendMessage
    # try:
    #     url = url_dict[event.message.text.upper()]
    #     message = TextSendMessage(text=url)
    # except:
    #     message = TextSendMessage(text=event.message.text)
    #
    #
    # # 回覆訊息
    # LINE_BOT.reply_message(event.reply_token, message)

