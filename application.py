from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError




app = Flask(__name__)

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

LINE_SECRET = "284c517b44f5909886dcf9523141a054"
LINE_TOKEN = "U05137bec0bb83f4aff678584bb4d3cc9"
LINE_BOT = LineBotApi(LINE_TOKEN)
HANDLER = WebhookHandler(LINE_SECRET)