from flask import Flask, render_template

app = Flask(__name__)

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/models")
def models():
    return render_template("models.html")

@app.route("/models/hf")
def hf():
    return render_template("huggingface.html")