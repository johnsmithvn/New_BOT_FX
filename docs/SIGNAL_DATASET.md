# Signal Dataset

## Purpose
Collection of representative signal message formats for parser testing.
Separate each signal block with a blank line.

## Standard Formats

GOLD BUY @ 2030 SL 2020 TP 2040 TP2 2050 TP3 2060

XAUUSD SELL 2045 SL 2055 TP1 2035 TP2 2025

EURUSD BUY 1.0850
SL 1.0800
TP1 1.0900
TP2 1.0950

GBPUSD SELL LIMIT 1.2700
SL 1.2750
TP 1.2650

## Market Execution

GOLD BUY NOW SL 2020 TP 2040

XAUUSD BUY MARKET
SL: 2015
TP: 2045

EURUSD SELL CMP
SL: 1.0900
TP: 1.0800

## With Entry Price Keywords

GOLD BUY
ENTRY PRICE: 2030
SL: 2020
TP: 2040

EURUSD SELL
ENTRY: 1.0850
STOP LOSS: 1.0900
TAKE PROFIT: 1.0800

## Limit / Stop Orders

XAUUSD BUY LIMIT 2020
SL 2010
TP1 2030
TP2 2040

GBPJPY SELL STOP 188.50
SL 189.00
TP 188.00

## Slash-Separated Symbols

XAU/USD BUY 2030
SL 2020
TP 2040

EUR/USD SELL 1.0850
SL 1.0900
TP 1.0800

## Aliases

GOLD SELL 2045
SL 2055
TP 2035

BITCOIN BUY 65000
SL 64000
TP 66000

## Multi-Line Formats

📊 SIGNAL ALERT 📊
GOLD BUY
Entry: 2030
SL: 2020
TP1: 2040
TP2: 2050
TP3: 2060

🔥 HOT SIGNAL 🔥
EURUSD SELL @ 1.0850
Stop Loss: 1.0900
Take Profit 1: 1.0800
Take Profit 2: 1.0750

## Edge Cases — Should Parse Successfully

GOLD    BUY   2030   SL  2020  TP  2040

gold buy 2030 sl 2020 tp 2040

XAUUSD BUY 2030.50 SL 2020.25 TP 2040.75

## Edge Cases — Should Fail Gracefully

hello world this is not a signal

BUY (missing symbol)

GOLD (missing side)

random text with no pattern at all 12345

## Noisy Messages

🚀🚀🚀 GOLD BUY 2030 🎯 SL 2020 💰 TP 2040 TP2 2050 🔥🔥

✅ EURUSD SELL @ 1.0850 ✅
⛔ SL: 1.0900
🎯 TP1: 1.0800
🎯 TP2: 1.0750
