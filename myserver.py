    from flask import flask
    from threading import thread, Thread

    app = flask('')

    @app.route('/')
    def home():
        return "Server is running!"

    def run()ซ
      app.run(host='0.0.0.0',port=8080)

    def sever_on():
        t = Thread(target=run)
        t.start()