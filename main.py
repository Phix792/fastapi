from fastapi import FastAPI
import MetaTrader5 as mt5

app = FastAPI()

if not mt5.initialize():
    print("MT5 Initialization failed")

# 1. Get Account Status
@app.get("/status")
def get_status():
    account_info = mt5.account_info()
    if account_info is None:
        return {"status": "error", "message": "MT5 Terminal not logged in"}
    return {
        "status": "online",
        "login": account_info.login,
        "balance": account_info.balance,
        "equity": account_info.equity,
        "margin_free": account_info.margin_free,
        "server": account_info.server
    }

# 2. Get All Open Positions
@app.get("/positions")
def get_positions():
    positions = mt5.positions_get()
    if positions is None or len(positions) == 0:
        return {"positions": []}
    
    pos_list = []
    for pos in positions:
        pos_list.append({
            "ticket": pos.ticket,
            "symbol": pos.symbol,
            "type": "BUY" if pos.type == 0 else "SELL",
            "volume": pos.volume,
            "price_open": pos.price_open,
            "sl": pos.sl,
            "tp": pos.tp,
            "profit": pos.profit
        })
    return {"positions": pos_list}

# 3. Open New Trade
@app.post("/trade")
def place_trade(data: dict):
    symbol = data.get("symbol", "EURUSD")
    action = data.get("action", "BUY")
    volume = float(data.get("volume", 0.01))
    
    order_type = mt5.ORDER_TYPE_BUY if action.upper() == "BUY" else mt5.ORDER_TYPE_SELL
    tick = mt5.symbol_info_tick(symbol)
    if tick is None:
        return {"status": "error", "message": f"Symbol {symbol} not found"}
        
    price = tick.ask if action.upper() == "BUY" else tick.bid
    
    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": volume,
        "type": order_type,
        "price": price,
        "sl": float(data.get("sl", 0.0)),
        "tp": float(data.get("tp", 0.0)),
        "deviation": 20,
        "magic": 100001,
        "comment": "API Trade",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }
    
    result = mt5.order_send(request)
    if result.retcode != mt5.TRADE_RETCODE_DONE:
        return {"status": "error", "message": f"Trade failed: {result.comment}"}
        
    return {"status": "success", "ticket": result.order, "price": result.price}

# 4. Modify SL and TP
@app.post("/position/modify")
def modify_position(data: dict):
    ticket = int(data.get("ticket"))
    sl = float(data.get("sl", 0.0))
    tp = float(data.get("tp", 0.0))

    position = mt5.positions_get(ticket=ticket)
    if not position:
        return {"status": "error", "message": f"Position #{ticket} not found"}

    pos = position[0]
    request = {
        "action": mt5.TRADE_ACTION_SLTP,
        "position": ticket,
        "symbol": pos.symbol,
        "sl": sl,
        "tp": tp,
    }

    result = mt5.order_send(request)
    if result.retcode != mt5.TRADE_RETCODE_DONE:
        return {"status": "error", "message": f"Modify failed: {result.comment}"}

    return {"status": "success", "ticket": ticket, "sl": sl, "tp": tp}

# 5. Close Position
@app.post("/position/close/{ticket}")
def close_position(ticket: int):
    position = mt5.positions_get(ticket=ticket)
    if not position:
        return {"status": "error", "message": f"Position #{ticket} not found"}

    pos = position[0]
    order_type = mt5.ORDER_TYPE_SELL if pos.type == 0 else mt5.ORDER_TYPE_BUY
    price = mt5.symbol_info_tick(pos.symbol).bid if pos.type == 0 else mt5.symbol_info_tick(pos.symbol).ask

    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "position": ticket,
        "symbol": pos.symbol,
        "volume": pos.volume,
        "type": order_type,
        "price": price,
        "deviation": 20,
        "magic": 100001,
        "comment": "Close via API",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }

    result = mt5.order_send(request)
    if result.retcode != mt5.TRADE_RETCODE_DONE:
        return {"status": "error", "message": f"Close failed: {result.comment}"}

    return {"status": "success", "ticket": ticket, "price": result.price}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
