import busio
import board
import adafruit_dht
import serial
import time
import RPi.GPIO as GPIO
import neopixel
import adafruit_pca9685
import os

# github
import json
import subprocess
from datetime import datetime


fan = 23
pump = 22
# water pump
GPIO.setmode(GPIO.BCM)
GPIO.setup(fan,GPIO.OUT) 
GPIO.setup(pump,GPIO.OUT)

# roof servo
i2c = busio.I2C(board.SCL, board.SDA)
hat = adafruit_pca9685.PCA9685(i2c)

from adafruit_servokit import ServoKit
kit = ServoKit(channels=16)

kit.servo[0].set_pulse_width_range(700,2850)

# led
pixels = neopixel.NeoPixel(board.D13, 15)


# sensor tx rx
ser = serial.Serial("/dev/ttyAMA0", 115200, timeout=0.5)
ser.flush()


soil_moisture=0
rain_stat=0
intensity=0
temperature=0

soildry = 1023
soilwater = 0
R1 = soildry - soilwater

raindry = 1023
rainMax = 370
R2 = raindry-rainMax

high_intensity = 0
low_intensity = 1023
R3 = low_intensity - high_intensity


# motor
motor1a = 5
motor1b = 6
motor1en = 19

GPIO.setup(motor1a,GPIO.OUT)
GPIO.setup(motor1b,GPIO.OUT)
GPIO.setup(motor1en,GPIO.OUT)



hum_sensor = adafruit_dht.DHT11(board.D4, use_pulseio=False)

# 10s read once hum_tmp
hum_count=0

humidity = 0
        
fan_s=0
light_s=0
roof_s=0
pump_s=0
    
git_log = "sensor_log.json"
upload_interval=60
inter=0

def git_push():
    
    env = os.environ.copy()
    env["GIT_SSH_COMMAND"]=("ssh -i /home/pi/.ssh/id_rsa "
                            "-o StrictHostKeyChecking=no "
                            "-o IdentitiesOnly=yes "
                            "-o UserKnownHostsFile=/home/pi/.ssh/known_hosts"
    )
    
    env.pop("SSH_AUTH_SOCK", None)
    env.pop("SSH_AGENT_PID", None)
    
    subprocess.run(["git","config","--local","user.name", "659760ouo"],capture_output=True, env=env)
    subprocess.run(["git","config","--local","user.email", "jimmychanelouo@gmail.com"],capture_output=True, env=env)
    
    subprocess.run(["git","add","sensor_log.json"],capture_output=False, text=True, env=env)
    c_msg = f"auto update: {datetime.utcnow().isoformat()}"
    c_result = subprocess.run(["git","commit","-m", c_msg],capture_output=False, text=True, env=env)
    
    
    if c_result.returncode == 0:
        
        subprocess.run(["git","push", "origin", "main"],capture_output=False, text=True, env=env)
    
        print("sucessfully pushed------------------------------")
    else:
        print("Failed to push ---------------------------------")
        
def sensor_reading():
    global soil_moisture, rain_stat, intensity
    
    
    if ser.in_waiting>0:
            
            line = ser.readline().decode('utf-8').rstrip()
            if line.startswith("Data:"):
                try:
                    
                    data_part = line.replace("Data:","")
                    print(data_part)
                    sh, rain, light = map(int, data_part.split(","))
                    print(sh, "SH")
                    
                    soil_moisture = int(((soildry - sh)/R1)*100)
                    print("soil humidity:", soil_moisture ,"%")
#                     print("light RAW:", sh)
                    
                    rain_stat = int(((raindry - rain)/R2)*100)
                    print("Raining status:", rain_stat ,"%")
#                     print("rain RAW:", rain)
                    
                    intensity = int(((low_intensity - light)/R3)*100)
                    print("light intensity:", intensity ,"%")
#                     print("light RAW:", light)
            
                except ValueError:
                    print('ValueError')
                
                
#     super important , delete the old data for faster reading
    ser.reset_input_buffer()
    

def open_fan():
    global fan_s
    fan_s = 1
    GPIO.output(fan,GPIO.HIGH)
    print('Fan spinning')
    
def close_fan():
    global fan_s
    fan_s = 0
    GPIO.output(fan,GPIO.LOW)
    print('Fan stop')
    
def pump_on():
    global pump_s
    pump_s = 1
#     pump
    GPIO.output(pump,GPIO.HIGH)
    
#     print("Going clockwise")
    GPIO.output(motor1a, GPIO.LOW)
    GPIO.output(motor1b, GPIO.HIGH)
    GPIO.output(motor1en, GPIO.HIGH)
    time.sleep(0.3)                                                                                                                                                                                                    
    GPIO.output(motor1en, GPIO.LOW)

#     print("Going counter clockwise")
    GPIO.output(motor1a, GPIO.HIGH)
    GPIO.output(motor1b, GPIO.LOW)
    GPIO.output(motor1en, GPIO.HIGH)
    time.sleep(0.3)
    GPIO.output(motor1en, GPIO.LOW)
    print('Spraying water')
    
    
def pump_off():
    global pump_s
    pump_s = 0
    GPIO.output(pump,GPIO.LOW)
    print('Pump stop')
    
    
def open_roof():
    global roof_s
    roof_s =1
    kit.servo[0].angle = 0
    print('Roof opened')
#     time.sleep(1)
    kit.servo[0].angle = 160
#     time.sleep(1)

def close_roof():
    global roof_s
    roof_s =0
    kit.servo[0].angle = 0
    print('Roof closed')
#     time.sleep(1)
    


def hum_tmp():
    global humidity, temperature
    try:
       
        humidity, temperature = hum_sensor.humidity, hum_sensor.temperature
        print('Humidity:',humidity, 'Temperature',temperature)
    except RuntimeError:
        return None, None
    
def light_on():
    global light_s
    light_s = 1
    pixels.fill((128,128,128))
    pixels.show()
    

def light_off():
    global light_s
    light_s = 0
    pixels.fill((0,0,0))
    pixels.show()
   

print("Start reading light intensity, rain status and soil moisture")

def check_env():
    
    sensor_reading()
    
    if soil_moisture< 50:
        pump_on()
    else:
        pump_off()
    
    
    if intensity < 80:
        light_on()
    else:
        light_off()
    
    if rain_stat > 30:
        open_roof()
    else:
        close_roof()
    
try:
    while True:
        check_env()
       
#         10s read once
        if hum_count < 9:
            hum_count+=1
        else:
            hum_tmp()
            hum_count=0
            
        if humidity >=80 :
            open_fan()
        else:
            close_fan()
      
        
        latest_data = {
            "timestamp":datetime.utcnow().isoformat(),
            "tmp": temperature,
            "hum":humidity,
            "sh":soil_moisture,
            "rain":rain_stat,
            "intensity":intensity,
            "pump":pump_s,
            "roof":roof_s,
            "light":light_s,
            "fan":fan_s
            
            
        }
        
        
        with open(git_log, "w", encoding="utf-8") as f:
            json.dump(latest_data, f, indent=2)
        
        if inter==10 :
            git_push()
            inter=0
            print("successfully pushed------------------")
        else:
            inter+=1
        time.sleep(1)
        
#         time.sleep(0.3)
except KeyboardInterrupt:
    GPIO.output(motor1en, GPIO.LOW)
    light_off()
    pump_off()
    close_roof()
    GPIO.cleanup()
    ser.close()


