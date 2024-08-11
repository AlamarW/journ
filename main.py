#!/usr/bin/python3

import cmd
import sqlite3
from tui_editor import TuiEditor 
from datetime import datetime
from os import system, name

conn = sqlite3.connect('journal.db')
cursor = conn.cursor()
cursor.execute("""CREATE TABLE user_info (
                user_id integer,
                writing_goal integer,
                )""")

conn.commit()
conn.close()

class User:
    
    def __init__(self, user_id, password, writing_goal):
        self.user_id = user_id
        self.password = password 
        self.writing_goal = writing_goal


class JournalSession:

    def __init__(self, session_id, journ_text, words_per_minute, accomplished_writing_goal, date):
        self.session_id = session_id
        self.journ_text = journal_text
        self.words_per_minute = words_per_minute
        self.accomplished_writing_goal = accomplished_writing_goal
        self.date = date 





class JournalingShell(cmd.Cmd):
    intro = "Welcome to Journaling Shell. Type help or ? to list commands.\nType `journ` to start!\nNote: if you haven't logged in, your journ won't be saved. \n"
    prompt = '(journ) '
    file = None

    def user_login(self, user_name, password):
        raise NotImplementedError

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
        
        time_string = str(elapsed_time)

        parsed_time = time_string.split(":")
        print(f"You've journalled for {parsed_time[0]} hour(s), {parsed_time[1]} minute(s), and {parsed_time[2][:2]} seconds")

    def streak_details(self, user_name, login):
        raise NotImplementedError

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
