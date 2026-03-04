import kivy
from kivy.app import App
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.label import Label
from kivy.uix.image import Image
from kivy.graphics import Color, Ellipse, StencilPush, StencilUse, StencilUnUse, StencilPop
from kivy.uix.scrollview import ScrollView
from kivy.clock import Clock

import sqlite3
import cv2
import datetime
import os

# ---------------- DATABASE SETUP ----------------
# Using advanced table structure and UNIQUE constraints from hoperescue.py
conn = sqlite3.connect("hope_rescue.db")
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users(
id INTEGER PRIMARY KEY AUTOINCREMENT,
username TEXT UNIQUE,
password TEXT)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS posts(
id INTEGER PRIMARY KEY AUTOINCREMENT,
username TEXT,
image_path TEXT,
description TEXT,
likes INTEGER DEFAULT 0)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS comments(
id INTEGER PRIMARY KEY AUTOINCREMENT,
post_id INTEGER,
comment TEXT)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS messages(
id INTEGER PRIMARY KEY AUTOINCREMENT,
sender TEXT,
message TEXT)
""")
conn.commit()

current_user = ""

# ---------------- LOGIN & SIGNUP SCREEN ----------------
class LoginScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        layout = BoxLayout(orientation="vertical", padding=40, spacing=20)

        # Logo Interface
        self.logo = Image (source='logo.png', size_hint=(1, 0.7), allow_stretch=True)
        layout.add_widget(self.logo)

        self.status_msg = Label(text="Welcome to Hope Rescue", size_hint_y=None, height=40)
        layout.add_widget(self.status_msg)

        self.username = TextInput(hint_text="Username", multiline=False, size_hint_y=0.2)
        self.password = TextInput(hint_text="Password", password=True, multiline=False, size_hint_y=0.2)

        login_btn = Button(text="Login", size_hint_y=0.2, background_color=(0.2, 0.6, 1, 1))
        register_btn = Button(text="Register / Sign Up", size_hint_y=0.2)

        login_btn.bind(on_press=self.login)
        register_btn.bind(on_press=self.register)

        layout.add_widget(self.username)
        layout.add_widget(self.password)
        layout.add_widget(login_btn)
        layout.add_widget(register_btn)
        self.add_widget(layout)

    def login(self, instance):
        global current_user
        user = self.username.text
        pwd = self.password.text
        cursor.execute("SELECT * FROM users WHERE username=? AND password=?", (user, pwd))
        result = cursor.fetchone()
        if result:
            current_user = user
            self.manager.current = "feed"
        else:
            self.status_msg.text = "Error: Invalid credentials"
            self.status_msg.color = (1, 0, 0, 1)

    def register(self, instance):
        user = self.username.text
        pwd = self.password.text
        if not user or not pwd:
            self.status_msg.text = "Fields cannot be empty"
            return
        try:
            # Registration logic to handle UNIQUE usernames from hoperescue.py
            cursor.execute("INSERT INTO users(username, password) VALUES(?,?)", (user, pwd))
            conn.commit()
            self.status_msg.text = "Success: Registered! Please Login."
            self.status_msg.color = (0, 1, 0, 1)
        except sqlite3.IntegrityError:
            self.status_msg.text = "Error: Username already exists"
            self.status_msg.color = (1, 0, 0, 1)

# ---------------- FEED SCREEN (WITH ACCURATE CAMERA) ----------------
class FeedScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.main_layout = BoxLayout(orientation="vertical")
        
        btns = BoxLayout(size_hint_y=0.1)
        post_btn = Button(text="Capture & Post")
        chat_btn = Button(text="Open Chat")
        post_btn.bind(on_press=self.trigger_capture)
        chat_btn.bind(on_press=lambda x: setattr(self.manager, 'current', 'chat'))
        
        btns.add_widget(post_btn)
        btns.add_widget(chat_btn)

        self.feed_layout = BoxLayout(orientation="vertical", size_hint_y=None)
        self.feed_layout.bind(minimum_height=self.feed_layout.setter('height'))
        scroll = ScrollView()
        scroll.add_widget(self.feed_layout)

        self.main_layout.add_widget(btns)
        self.main_layout.add_widget(scroll)
        self.add_widget(self.main_layout)
        self.load_feed()

    def trigger_capture(self, instance):
        # Improved capture: Verifies camera is opened before reading
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            print("Error: Could not open camera")
            return

        ret, frame = cap.read()
        if ret:
            # Filename using timestamp naming convention from hoperescue.py
            filename = f"animal_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}.jpg"
            cv2.imwrite(filename, frame)
            
            cursor.execute("INSERT INTO posts(username, image_path, description, likes) VALUES(?,?,?,0)",
                           (current_user, filename, "Animal rescue post"))
            conn.commit()
            self.load_feed()
        
        cap.release()

    def load_feed(self):
        self.feed_layout.clear_widgets()
        cursor.execute("SELECT * FROM posts ORDER BY id DESC")
        posts = cursor.fetchall()
        for post in posts:
            box = BoxLayout(orientation="vertical", size_hint_y=None, height=450, padding=10)
            if os.path.exists(post[2]):
                box.add_widget(Image(source=post[2]))
            
            info = Label(text=f"Posted by: {post[1]}", size_hint_y=0.1)
            like_btn = Button(text=f"Like ({post[4]})", size_hint_y=0.15)
            like_btn.bind(on_press=lambda x, p=post[0]: self.like_post(p))
            
            box.add_widget(info)
            box.add_widget(like_btn)
            self.feed_layout.add_widget(box)

    def like_post(self, post_id):
        cursor.execute("UPDATE posts SET likes=likes+1 WHERE id=?", (post_id,))
        conn.commit()
        self.load_feed()

# ---------------- CHAT SCREEN ----------------
class ChatScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        layout = BoxLayout(orientation="vertical")
        
        self.scroll_view = ScrollView()
        self.msg_list = BoxLayout(orientation="vertical", size_hint_y=None)
        self.msg_list.bind(minimum_height=self.msg_list.setter('height'))
        self.scroll_view.add_widget(self.msg_list)

        input_area = BoxLayout(size_hint_y=0.15)
        self.msg_input = TextInput(hint_text="Type a message...")
        send_btn = Button(text="Send", size_hint_x=0.2)
        send_btn.bind(on_press=self.send_msg)
        
        back_btn = Button(text="Back", size_hint_y=0.1)
        back_btn.bind(on_press=lambda x: setattr(self.manager, 'current', 'feed'))

        input_area.add_widget(self.msg_input)
        input_area.add_widget(send_btn)
        
        layout.add_widget(back_btn)
        layout.add_widget(self.scroll_view)
        layout.add_widget(input_area)
        self.add_widget(layout)

    def send_msg(self, instance):
        msg = self.msg_input.text
        if msg.strip():
            cursor.execute("INSERT INTO messages(sender, message) VALUES(?,?)", (current_user, msg))
            conn.commit()
            self.msg_list.add_widget(Label(text=f"{current_user}: {msg}", size_hint_y=None, height=40))
            self.msg_input.text = ""

# ---------------- MAIN APP ----------------
class HopeApp(App):
    def build(self):
        sm = ScreenManager()
        sm.add_widget(LoginScreen(name="login"))
        sm.add_widget(FeedScreen(name="feed"))
        sm.add_widget(ChatScreen(name="chat"))
        return sm

if __name__ == "__main__":
    HopeApp().run()
