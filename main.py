#!/usr/bin/python3

import cmd
import sqlite3
from tui_editor import TuiEditor 
from datetime import datetime
from os import system, name
import uuid

conn = sqlite3.connect('journal.db')
cursor = conn.cursor()
cursor.execute("""CREATE TABLE IF NOT EXISTS user_info (
                user_id integer,
                password text,
                writing_goal integer
                )""")

conn.commit()

cursor.execute("""CREATE TABLE IF NOT EXISTS journal_session (
               session_id integer,
               journal_text blob,
               words_per_minute real,
               date test,
               accomplished_writing_goal 
               )""")

conn.commit()

class User:
    
    def __init__(self, user_id, password, writing_goal):
        self.user_id = user_id
        self.password = password 
        self.writing_goal = writing_goal

    def register(self):
        print(self.user_id)
        print(self.password)

class JournalSession:

    def __init__(self, session_id, journ_text, words_per_minute, accomplished_writing_goal, date):
        self.session_id = session_id
        self.journ_text = journ_text
        self.words_per_minute = words_per_minute
        self.accomplished_writing_goal = accomplished_writing_goal
        self.date = date

class JournalingShell(cmd.Cmd):
    intro = "Welcome to Journaling Shell. Type help or ? to list commands.\nType `journ` to start!\nNote: if you haven't logged in, your journ won't be saved. \n"
    prompt = '(journ) '
    writing_goal = 0
    name = None

    def do_login(self,line):
        "Register and Login here!"
        #registration function needs to go here
        def confirm_login():
            def login():
                """Ask user for user name, check it against database"""
                user_name = input("What is your user name? ")
                user_data = cursor.execute("SELECT user_id, password, writing_goal FROM user_info WHERE user_id = ?",[user_name])
                user_data_grab = user_data.fetchone()
                password_actual = user_data_grab[1]
                password_attempt = input("What is your password? ")
                if password_actual == password_attempt:
                    JournalingShell.name = user_name
                    JournalingShell.writing_goal = user_data_grab[2]
                else:
                    print("invalid password")
                    login()

                return print("logged in")
            def register():
                user_name = input("choose your username ")
                password = input("Choose your password ")
                writing_goal = input("Write your daily writing goal (Using digits only) ")
                cursor.execute("INSERT INTO user_info VALUES (?, ? , ?)", [user_name, password, int(writing_goal)])
                conn.commit()
                print("Now log in to the system")
                login()

            has_registered = input("Have you set up a user name and password?(y/n) ")
            
            if has_registered.lower() == "y":
                login()

            elif has_registered.lower() == "n":
                print("not registered")
                register()
            else:
                print("input has to be either y or no")
                confirm_login()
                
        confirm_login()           
        #user_name = input("User name: ")
        #password = input("password: ")

        #user = User(user_name, password, 23)
        #user.register()


    def user_info(user_name):
        return True

    def do_journ(self, line):
        "Starts the Journalling interface"
        cmd.doc_header = "test"
        start_time = datetime.now()
        JournalingShell.clear()
        print("start journaling below. Press ctrl+S to save and quit")
        editor = TuiEditor()
        editor.show_line_numbers = True
        editor.edit()
        contents = editor.get_text()
        
        journal_length = len(contents.split())

        if journal_length >= 100:
            print(f"You've typed {journal_length} words. This is over your goal")
            
        else:
            print(f"You've typed {journal_length} words. This is under your goal")

        end_time = datetime.now()

        elapsed_time = end_time - start_time
        in_seconds = elapsed_time.total_seconds() 
        in_minutes = in_seconds/60
        time_string = str(elapsed_time)

        parsed_time = time_string.split(":")
        print(f"You've journalled for {parsed_time[0]} hour(s), {parsed_time[1]} minute(s), and {parsed_time[2][:2]} seconds")
        journ_wpm = round(journal_length / in_minutes, 1) 
        JournalSession.session_id = start_time
        JournalSession.journ_text = contents
        JournalSession.words_per_minute = journ_wpm
        JournalSession.date = end_time
        cursor.execute("INSERT INTO journal_session VALUES (?, ? , ?, ?, ?)", [JournalSession.session_id, JournalSession.journ_text, JournalSession.words_per_minute,JournalSession.date,True])
        conn.commit()
 

    def streak_details(self, user_name, login):
        raise NotImplementedError

       
    def do_test(self, line):
       "Check DB Status, should be two tables (DELETE BEFORE FINAL RELEASE"
       cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
       print(cursor.fetchall())
       conn.commit()
       cursor.execute("SELECT * FROM journal_session")
       print(cursor.fetchall())
       conn.commit()

    def save_journal(self, args):
        raise NotImplementedError

    def clear():
        if name =='nt':
            _ = system('cls')

        else:
            _ = system('clear')

    def do_EOF(self,line):
        return True
if __name__ == '__main__':
    JournalingShell.clear()
    JournalingShell().cmdloop()
    conn.close()
