import time
import pygetwindow as gw
import keyboard
import requests
import serial
import tkinter as tk
from tkinter import messagebox
import threading
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import os
from dotenv import load_dotenv
import serial.tools.list_ports

load_dotenv()

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

def find_arduino_port():
    ports = serial.tools.list_ports.comports()
    for port in ports:
        if 'Arduino' in port.description or 'CH340' in port.description or 'USB' in port.description:
            return port.device
    return None

def connect_to_arduino():
    global arduino, connection_lost
    
    arduino_port = find_arduino_port()
    if not arduino_port:
        arduino_port = 'COM3'
    
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

def check_arduino_connection():
    global arduino, connection_lost, last_heartbeat
    
    if arduino is None:
        return False
    
    try:
        if time.time() - last_heartbeat > 5:
            arduino.write("heartbeat\n".encode())
            last_heartbeat = time.time()
        
        if not arduino.is_open:
            return False
            
        return True
    except:
        return False

def handle_connection_loss():
    global connection_lost, session_active, result
    
    if not connection_lost:
        connection_lost = True
        print("🚨 ARDUINO DISCONNECTED! This counts as cheating!")
        
        if session_active:
            print("💔 Session terminated due to Arduino disconnection!")
            session_active = False
            result = "fail"
            
            popup_thread = threading.Thread(target=show_disconnection_popup)
            popup_thread.daemon = True
            popup_thread.start()
            
            sites_list = ", ".join(distracting_sites) if distracting_sites else "None detected"
            email_body = f"🚨 CHEATING ATTEMPT DETECTED!\n\nNaman disconnected the Arduino during an active focus session.\n\nThis is a clear attempt to bypass the monitoring system.\n\nSession details:\n- Distractions detected: {distraction_count}\n- Sites visited: {sites_list}\n\nPlease address this immediately.\n\nRegards,\nFocus Session Monitor"
            
            parent_email = os.getenv('PARENT_EMAIL', "")
            send_email(
                to_email=parent_email,
                subject="🚨 URGENT: Arduino Disconnection During Focus Session",
                body=email_body
            )

def send_tamper_alert_email():
    parent_email = os.getenv('PARENT_EMAIL', "")
    
    email_body = (
        "🚨 CANDY DOOR TAMPER ATTEMPT DETECTED!\n\n"
        "The anti-tamper system has detected someone trying to access the candy compartment "
        "without properly unlocking it.\n\n"
        "Details:\n"
        "- Object detected within 10cm of candy door\n"
        "- Sustained attempt for more than 5 seconds\n"
        "- Potentiometer lock was NOT in unlocked position\n\n"
        "This appears to be an unauthorized attempt to access the candy.\n\n"
        "Please check on the situation immediately.\n\n"
        "Regards,\nFocus Session Anti-Tamper System"
    )
    
    success = send_email(
        to_email=parent_email,
        subject="🚨 URGENT: Candy Door Tamper Attempt Detected",
        body=email_body
    )
    
    if success:
        print("✅ Tamper alert email sent successfully!")
    else:
        print("❌ Failed to send tamper alert email!")
    
    return success

def show_tamper_popup():
    """Show popup warning about tamper attempt"""
    root = tk.Tk()
    root.withdraw()
    messagebox.showerror(
        "TAMPER ATTEMPT DETECTED!", 
        "🚨 UNAUTHORIZED CANDY ACCESS DETECTED!\n\n"
        "Someone is trying to access the candy without unlocking!\n\n"
        "Email sent to parent!"
    )
    root.destroy()

def show_disconnection_popup():
    root = tk.Tk()
    root.withdraw()
    messagebox.showerror("CHEATING DETECTED!", "🚨 ARDUINO DISCONNECTED!\n\nThis counts as cheating!\nSession terminated and email sent.")
    root.destroy()

def reconnect_arduino():
    global arduino
    
    print("🔄 Attempting to reconnect to Arduino...")
    if arduino:
        try:
            arduino.close()
        except:
            pass
    
    return connect_to_arduino()

if not connect_to_arduino():
    print("❌ Could not connect to Arduino. Please check connection and try again.")
    exit(1)

def send_email(to_email, subject, body, sender_email=None, sender_password=None, 
               smtp_server="smtp.gmail.com", smtp_port=587, attachment_path=None):
    if sender_email is None:
        sender_email = os.getenv('EMAIL_ADDRESS')
    if sender_password is None:
        sender_password = os.getenv('EMAIL_PASSWORD')
        
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
                part.add_header(
                    'Content-Disposition',
                    f'attachment; filename= {os.path.basename(attachment_path)}'
                )
                msg.attach(part)
        
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(sender_email, sender_password)
        
        text = msg.as_string()
        server.sendmail(sender_email, to_email, text)
        server.quit()
        
        print(f"Email sent successfully to {to_email}")
        return True
        
    except Exception as e:
        print(f"Error sending email: {str(e)}")
        return False

def show_warning_popup(count, punishment):
    root = tk.Tk()
    root.withdraw()
    
    warning_msg = f"🚨 DISTRACTION WARNING!\n\nDistraction Count: {count}\n\nCurrent Punishment: {punishment}\n\nGet back to work!"
    messagebox.showwarning("FOCUS WARNING", warning_msg)
    root.destroy()

def determine_punishment(count):
    if count == 1:
        return "Session extended by 10 minutes"
    elif count == 2:
        return "Session extended by 20 min + Candy locked 10 min"
    elif count >= 3:
        return "Session ended + Email sent + Candy locked 20 min"
    return ""

def is_distracting(title):
    prompt = (
        f'A user is trying to stay focused on work. If this window title is distracting (e.g., social media, irrelevant videos, gaming), respond ONLY with "X". '
        f'Otherwise, respond ONLY with "A".\n\n'
        f'Title: "{title}"'
    )
    try:
        endpoint = os.getenv("API_ENDPOINT")
        response = requests.post(
            endpoint,
            headers={'Content-Type': 'application/json'},
            json={"messages": [{"role": "user", "content": prompt}]}
        )
        reply = response.json()['choices'][0]['message']['content'].strip().upper()
        print(f"AI Response for '{title}': {reply}")
        return reply == 'X'
    except Exception as e:
        print(f"AI call failed: {e}")
        return False

def handle_distraction(title):
    global distraction_count, current_punishment, result, session_active, distracting_sites
    
    distraction_count += 1
    distracting_sites.append(title)
    current_punishment = determine_punishment(distraction_count)
    
    print(f"🚨 DISTRACTION #{distraction_count} DETECTED: {title}")
    print(f"Current punishment: {current_punishment}")
    
    keyboard.press_and_release('ctrl+w')
    
    if arduino and not connection_lost:
        arduino.write("buzzer\n".encode())
        
        truncated_title = title[:20] if len(title) > 20 else title
        arduino.write(f"distraction_{distraction_count}_{truncated_title}\n".encode())
    
    popup_thread = threading.Thread(target=show_warning_popup, args=(distraction_count, current_punishment))
    popup_thread.daemon = True
    popup_thread.start()
    
    if arduino and not connection_lost:
        if distraction_count == 1:
            arduino.write("extend_10\n".encode())
            print("⏰ Session extended by 10 minutes")
            
        elif distraction_count == 2:
            arduino.write("extend_20\n".encode())
            arduino.write("candy_lock_10\n".encode())
            print("⏰ Session extended by 20 minutes + Candy locked for 10 minutes")
            
        elif distraction_count >= 3:
            print("🚨 MAXIMUM INFRACTIONS REACHED!")
            
            sites_list = ", ".join(distracting_sites)
            email_body = f"Hi,\nNaman was off task during their focus session. They opened the following distracting content: {sites_list}\n\nTotal infractions: {distraction_count}\n\nPlease check on them.\n\nRegards,\nFocusMaxxer Activity"
            
            parent_email = os.getenv('PARENT_EMAIL', "")
            send_email(
                to_email=parent_email,
                subject="Focus Session - Multiple Distractions Detected",
                body=email_body
            )
            
            arduino.write("end_session\n".encode())
            arduino.write("candy_lock_20\n".encode())
            result = "fail"
            session_active = False
            print("💔 Session terminated due to excessive distractions!")
    else:
        print("⚠️ Arduino disconnected - cannot apply punishment!")

print("🎯 Start a focus session on your Arduino to begin!")
print("🛡️ Anti-tamper system is active - candy door is protected!")

while True:
    try:
        if not check_arduino_connection():
            handle_connection_loss()
            
            time.sleep(5)
            if reconnect_arduino():
                print("✅ Arduino reconnected!")
            continue
        
        if arduino and arduino.in_waiting:
            msg = arduino.readline().decode().strip()
            print(f"📨 Arduino says: '{msg}'")
            
            if msg == "heartbeat_ok":
                continue
            elif msg == "tamper_email":
                print("🚨 TAMPER EMAIL REQUEST RECEIVED!")
                
                # Send tamper alert email in separate thread
                email_thread = threading.Thread(target=send_tamper_alert_email)
                email_thread.daemon = True
                email_thread.start()
                
                # Show popup warning
                popup_thread = threading.Thread(target=show_tamper_popup)
                popup_thread.daemon = True
                popup_thread.start()
                
                continue
            
            if "Starting countdown for" in msg:
                print("🎯 Focus session started! Now monitoring your behavior...")
                session_active = True
                result = "success"
                distraction_count = 0
                distracting_sites.clear()
                current_punishment = ""
                prev_title = ''
                connection_lost = False
                
                try:
                    original_focus_time = int(msg.split("for ")[1].split(" minutes")[0])
                    print(f"📝 Original focus time: {original_focus_time} minutes")
                except:
                    original_focus_time = 0
            
            elif msg == "done":
                print("⏰ Focus session completed!")
                session_active = False
                
                if distraction_count > 0:
                    print(f"📊 SESSION SUMMARY:")
                    print(f"   Total Distractions: {distraction_count}")
                    print(f"   Sites Visited: {', '.join(distracting_sites)}")
                    print(f"   Final Punishment: {current_punishment}")
                    
                    if arduino and not connection_lost:
                        arduino.write(f"summary_{distraction_count}\n".encode())
                        time.sleep(2)
                
                print(f"📤 Sending final result to Arduino: {result}")
                if arduino and not connection_lost:
                    arduino.write((result + "\n").encode())
                
                if result == "success":
                    if distraction_count == 0:
                        print("✅ Perfect! No distractions detected!")
                    else:
                        print("✅ Session completed despite distractions!")
                else:
                    print("❌ Session failed due to excessive distractions!")

        if session_active and not connection_lost:
            window = gw.getActiveWindow()
            if window and window.title:
                title = window.title.strip()
                if title != prev_title and title:
                    print(f"🔍 Monitoring: {title}")
                    if is_distracting(title):
                        handle_distraction(title)
                    prev_title = title

        time.sleep(0.5)

    except KeyboardInterrupt:
        print("\n👋 Shutting down...")
        if arduino:
            arduino.close()
        break
    except Exception as e:
        print(f"❌ Error: {e}")
        if "device reports readiness to read but returned no data" in str(e) or "could not open port" in str(e):
            handle_connection_loss()