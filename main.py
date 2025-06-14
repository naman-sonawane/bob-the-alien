# Import necessary libraries
import time
import pygetwindow as gw  # To get the current active window title
import keyboard  # To simulate keyboard actions (like closing tabs)
import requests  # To send requests to AI endpoint
import serial  # For communication with Arduino
import tkinter as tk  # GUI for popups
from tkinter import messagebox
import threading  # For running tasks in background
import smtplib  # For sending emails
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import os
from dotenv import load_dotenv  # To load secrets from a .env file
import serial.tools.list_ports  # To detect Arduino port

load_dotenv()

# Initial values and setup
prev_title = ''
session_active = False
result = "success"
distraction_count = 0
distracting_sites = []
original_focus_time = 0
current_punishment = ""
arduino = None
connection_lost = False
last_heartbeat = time.time()

# Try to find which port the Arduino is connected to
def find_arduino_port():
    ports = serial.tools.list_ports.comports()
    for port in ports:
        if 'Arduino' in port.description or 'CH340' in port.description or 'USB' in port.description:
            return port.device
    return None

# Connect to Arduino
def connect_to_arduino():
    global arduino, connection_lost
    arduino_port = find_arduino_port() or 'COM3'
    try:
        print(f"Attempting to connect to Arduino on {arduino_port}...")
        arduino = serial.Serial(arduino_port, 9600, timeout=1)
        time.sleep(3)
        connection_lost = False
        print("✅ Connected! Ready for focus sessions.")
        return True
    except Exception as e:
        print(f"❌ Failed to connect to Arduino: {e}")
        return False

# Check if Arduino is still connected
def check_arduino_connection():
    global arduino, connection_lost, last_heartbeat
    if arduino is None:
        return False
    try:
        if time.time() - last_heartbeat > 5:
            arduino.write("heartbeat\n".encode())  # Send ping to Arduino
            last_heartbeat = time.time()
        return arduino.is_open
    except:
        return False

# Handle situation where Arduino disconnects
def handle_connection_loss():
    global connection_lost, session_active, result
    if not connection_lost:
        connection_lost = True
        print("🚨 ARDUINO DISCONNECTED! This counts as cheating!")
        if session_active:
            session_active = False
            result = "fail"
            threading.Thread(target=show_disconnection_popup, daemon=True).start()
            sites_list = ", ".join(distracting_sites) if distracting_sites else "None detected"
            email_body = f"🚨 CHEATING ATTEMPT DETECTED!\n\nNaman disconnected the Arduino during an active focus session..."
            send_email(
                to_email=os.getenv('PARENT_EMAIL', ""),
                subject="🚨 URGENT: Arduino Disconnection During Focus Session",
                body=email_body
            )

# Send email alert when tamper attempt is detected
def send_tamper_alert_email():
    parent_email = os.getenv('PARENT_EMAIL', "")
    email_body = (
        "🚨 CANDY DOOR TAMPER ATTEMPT DETECTED!\n\n"
        "Unauthorized attempt to access the candy detected."
    )
    return send_email(parent_email, "🚨 URGENT: Candy Door Tamper Attempt Detected", email_body)

# Show popup if candy tamper is detected
def show_tamper_popup():
    root = tk.Tk()
    root.withdraw()
    messagebox.showerror("TAMPER ATTEMPT DETECTED!", "🚨 UNAUTHORIZED CANDY ACCESS DETECTED!\n\nEmail sent to parent!")
    root.destroy()

# Show popup if Arduino is unplugged during session
def show_disconnection_popup():
    root = tk.Tk()
    root.withdraw()
    messagebox.showerror("CHEATING DETECTED!", "🚨 ARDUINO DISCONNECTED!\n\nSession terminated and email sent.")
    root.destroy()

# Try to reconnect Arduino
def reconnect_arduino():
    global arduino
    print("🔄 Attempting to reconnect to Arduino...")
    if arduino:
        try:
            arduino.close()
        except:
            pass
    return connect_to_arduino()

# Connect initially
if not connect_to_arduino():
    print("❌ Could not connect to Arduino. Please check connection and try again.")
    exit(1)

# Send email with optional attachment
def send_email(to_email, subject, body, sender_email=None, sender_password=None,
               smtp_server="smtp.gmail.com", smtp_port=587, attachment_path=None):
    sender_email = sender_email or os.getenv('EMAIL_ADDRESS')
    sender_password = sender_password or os.getenv('EMAIL_PASSWORD')
    if not sender_email or not sender_password:
        print("Error: Email credentials not provided")
        return False
    try:
        msg = MIMEMultipart()
        msg['From'] = sender_email
        msg['To'] = to_email
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))

        if attachment_path and os.path.exists(attachment_path):
            with open(attachment_path, "rb") as attachment:
                part = MIMEBase('application', 'octet-stream')
                part.set_payload(attachment.read())
                encoders.encode_base64(part)
                part.add_header('Content-Disposition', f'attachment; filename= {os.path.basename(attachment_path)}')
                msg.attach(part)

        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(sender_email, sender_password)
        server.sendmail(sender_email, to_email, msg.as_string())
        server.quit()
        print(f"Email sent successfully to {to_email}")
        return True
    except Exception as e:
        print(f"Error sending email: {str(e)}")
        return False

# Show popup when distraction is detected
def show_warning_popup(count, punishment):
    root = tk.Tk()
    root.withdraw()
    messagebox.showwarning("FOCUS WARNING", f"🚨 DISTRACTION WARNING!\n\nDistraction Count: {count}\nCurrent Punishment: {punishment}")
    root.destroy()

# Decide punishment based on number of distractions
def determine_punishment(count):
    if count == 1:
        return "Session extended by 10 minutes"
    elif count == 2:
        return "Session extended by 20 min + Candy locked 10 min"
    elif count >= 3:
        return "Session ended + Email sent + Candy locked 20 min"
    return ""

# Ask AI if the current window title is distracting
def is_distracting(title):
    prompt = f'A user is trying to stay focused on work...Title: "{title}"'
    try:
        endpoint = os.getenv("API_ENDPOINT")
        response = requests.post(endpoint, headers={'Content-Type': 'application/json'}, json={"messages": [{"role": "user", "content": prompt}]})
        reply = response.json()['choices'][0]['message']['content'].strip().upper()
        print(f"AI Response for '{title}': {reply}")
        return reply == 'X'
    except Exception as e:
        print(f"AI call failed: {e}")
        return False

# Handle what happens if a distraction is detected
def handle_distraction(title):
    global distraction_count, current_punishment, result, session_active, distracting_sites
    distraction_count += 1
    distracting_sites.append(title)
    current_punishment = determine_punishment(distraction_count)
    print(f"🚨 DISTRACTION #{distraction_count} DETECTED: {title}")
    keyboard.press_and_release('ctrl+w')  # Close current tab/window
    if arduino and not connection_lost:
        arduino.write("buzzer\n".encode())  # Buzz warning
        arduino.write(f"distraction_{distraction_count}_{title[:20]}\n".encode())
    threading.Thread(target=show_warning_popup, args=(distraction_count, current_punishment), daemon=True).start()
    if arduino and not connection_lost:
        if distraction_count == 1:
            arduino.write("extend_10\n".encode())
        elif distraction_count == 2:
            arduino.write("extend_20\n".encode())
            arduino.write("candy_lock_10\n".encode())
        elif distraction_count >= 3:
            send_email(
                os.getenv('PARENT_EMAIL', ""),
                "Focus Session - Multiple Distractions Detected",
                f"Naman was off task. Distractions: {', '.join(distracting_sites)}"
            )
            arduino.write("end_session\n".encode())
            arduino.write("candy_lock_20\n".encode())
            result = "fail"
            session_active = False

# Start message
print("🎯 Start a focus session on your Arduino to begin!")
print("🛡️ Anti-tamper system is active - candy door is protected!")

# Main loop to monitor focus session
while True:
    try:
        if not check_arduino_connection():
            handle_connection_loss()
            time.sleep(5)
            if reconnect_arduino():
                print("✅ Arduino reconnected!")
            continue

        # Read messages from Arduino
        if arduino and arduino.in_waiting:
            msg = arduino.readline().decode().strip()
            print(f"📨 Arduino says: '{msg}'")

            if msg == "heartbeat_ok":
                continue
            elif msg == "tamper_email":
                threading.Thread(target=send_tamper_alert_email, daemon=True).start()
                threading.Thread(target=show_tamper_popup, daemon=True).start()
                continue
            elif "Starting countdown for" in msg:
                print("🎯 Focus session started! Now monitoring...")
                session_active = True
                result = "success"
                distraction_count = 0
                distracting_sites.clear()
                prev_title = ''
                try:
                    original_focus_time = int(msg.split("for ")[1].split(" minutes")[0])
                except:
                    original_focus_time = 0
            elif msg == "done":
                print("⏰ Focus session completed!")
                session_active = False
                if distraction_count > 0:
                    print(f"📊 SESSION SUMMARY: {distraction_count} distractions.")
                    if arduino and not connection_lost:
                        arduino.write(f"summary_{distraction_count}\n".encode())
                        time.sleep(2)
                if arduino and not connection_lost:
                    arduino.write((result + "\n").encode())
                print("✅ Session result:", result)

        # Check current window title for distractions
        if session_active and not connection_lost:
            window = gw.getActiveWindow()
            if window and window.title:
                title = window.title.strip()
                if title != prev_title:
                    print(f"🔍 Monitoring: {title}")
                    if is_distracting(title):
                        handle_distraction(title)
                    prev_title = title

        time.sleep(0.5)  # Check every half second

    except KeyboardInterrupt:
        print("\n👋 Shutting down...")
        if arduino:
            arduino.close()
        break
    except Exception as e:
        print(f"❌ Error: {e}")
        if "device reports readiness to read but returned no data" in str(e) or "could not open port" in str(e):
            handle_connection_loss()
