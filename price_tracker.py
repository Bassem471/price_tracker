import os
import re
import requests
from bs4 import BeautifulSoup
from twilio.rest import Client

target_URL = "https://www.games2egypt.com/Product/40744/gamesir-g7-se-wired-controller-vibrant-orange"
Price_Selector = "h4.mb-2"
Price_Cache_File = "last_price.txt"

Twilio_Account_SID = os.environ.get("TWILIO_ACCOUNT_SID")
Twilio_Auth_Code = os.environ.get("TWILIO_AUTH_TOKEN")
Phone = os.environ.get("MY_PHONE_NUMBER")
Twilio_Phone_Number = os.environ.get("TWILIO_PHONE_NUMBER")

Alert_Channel = "sms"

print("--- STARTING PRICE TRACKER SCRIPT ---", flush=True)


def extract_price(text: str) -> float | None:
    """Extracts the first floating-point number from text."""
    cleaned = text.replace(",", "")
    match = re.search(r"\d+\.?\d*", cleaned)
    return float(match.group()) if match else None


def load_previous_price() -> float | None:
    """Reads the most recent price from the last line of the cache file."""
    if os.path.exists(Price_Cache_File):
        with open(Price_Cache_File, "r") as f:
            lines = [line.strip() for line in f.readlines() if line.strip()]
            if lines:
                try:
                    return float(lines[-1])
                except ValueError:
                    return None
    return None


def save_current_price(price: float):
    """Saves the current price as the single active reference price."""
    with open(Price_Cache_File, "w") as f:
        f.write(f"{price:.2f}\n")
    print(f"Logged current price (EGP {price:.2f}) to {Price_Cache_File}", flush=True)


def send_twilio_alert(message: str):
    """Dispatches SMS or WhatsApp alert via Twilio API."""
    if not Twilio_Account_SID or not Twilio_Auth_Code:
        print("TWILIO ERROR: Missing API keys in environment variables!", flush=True)
        return

    print("Attempting to connect to Twilio API...", flush=True)
    client = Client(Twilio_Account_SID, Twilio_Auth_Code)

    from_number = f"whatsapp:{Twilio_Phone_Number}" if Alert_Channel == "whatsapp" else Twilio_Phone_Number
    to_number = f"whatsapp:{Phone}" if Alert_Channel == "whatsapp" else Phone

    try:
        msg = client.messages.create(body=message, from_=from_number, to=to_number)
        print(f"SUCCESS! Alert sent via {Alert_Channel}! (SID: {msg.sid})", flush=True)
    except Exception as e:
        print(f"TWILIO ERROR: {e}", flush=True)


def check_for_sale():
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "en-US,en;q=0.9",
    }
    print("Fetching Games 2 Egypt product page...", flush=True)

    try:
        response = requests.get(target_URL, headers=headers, timeout=10)
    except Exception as e:
        print(f"NETWORK ERROR fetching URL: {e}", flush=True)
        return

    if response.status_code != 200:
        print(f"Failed to fetch page. HTTP Status Code: {response.status_code}", flush=True)
        return

    soup = BeautifulSoup(response.text, "html.parser")

    save_badge = soup.find(lambda tag: tag.name in ["span", "div", "p"] and "Save " in tag.text)
    savings_text = save_badge.get_text(strip=True) if save_badge else None

    price_element = soup.select_one(Price_Selector) or soup.find(
        lambda tag: tag.name in ["span", "div", "h3", "p"] and "EGP" in tag.text
    )

    if not price_element:
        print("Couldn't load price tag on the page.", flush=True)
        return

    current_price = extract_price(price_element.get_text())
    if current_price is None:
        print("Found price element but failed to parse number.", flush=True)
        return

    previous_price = load_previous_price()
    print(f"Current Price: EGP {current_price:.2f} | Last recorded: {previous_price}", flush=True)

    is_price_dropped = (previous_price is not None) and (current_price < previous_price)

    if is_price_dropped:
        discount_info = f" ({savings_text})" if savings_text else ""
        alert_msg = (
            f"🔥 GAMES 2 EGYPT PRICE DROP! 🔥\n"
            f"Price dropped from EGP {previous_price:.2f} to EGP {current_price:.2f}{discount_info}!\n"
            f"Link: {target_URL}"
        )
        print("New price drop detected! Triggering SMS alert...", flush=True)
        send_twilio_alert(alert_msg)
    elif previous_price is None:
        print("Baseline established! First price logged; skipping SMS for now.", flush=True)
    else:
        print("Price unchanged or higher. Skipping SMS to save Twilio credits.", flush=True)

    save_current_price(current_price)


if __name__ == "__main__":
    check_for_sale()