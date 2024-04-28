import asyncio
import websocket

ws = websocket.WebSocketApp('wss://api-pub.bitfinex.com/ws/2')

ws.on_open = lambda self: self.send('{ "event": "subscribe", "channel": "ticker", "symbol": "tBTCUSD"}')

ws.on_message = lambda self, evt:  print (evt)
