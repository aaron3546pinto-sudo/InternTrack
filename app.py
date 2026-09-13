from core import create_app, socketio

# Instantiate the Flask application using the factory pattern
app = create_app()

if __name__ == "__main__":
    # Start the application using SocketIO's development server instead of app.run()
    # This enables real-time WebSocket capabilities alongside standard HTTP routes
    socketio.run(app, debug=True)
