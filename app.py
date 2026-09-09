from core import create_app, socketio

app = create_app()

if __name__ == "__main__":
    # We now run the app wrapped in the WebSocket server
    socketio.run(app, debug=True)