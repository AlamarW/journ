import cmd
import sqlite3
from datetime import datetime, date
from os import system, name, getenv, remove, path, listdir, getcwd
import subprocess
import tempfile
import time

conn = sqlite3.connect("journal.db")
cursor = conn.cursor()
cursor.execute(
    """CREATE TABLE IF NOT EXISTS user_info (
                user_id text,
                password text,
                writing_goal integer
                )"""
)

conn.commit()

cursor.execute(
    """CREATE TABLE IF NOT EXISTS journal_session (
               session_id text PRIMARY KEY,
               user_id text,
               journal_text blob,
               words_per_minute real,
               date text,
               accomplished_writing_goal
               )"""
)

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
    def __init__(
        self, session_id, user_id, journ_text, words_per_minute, accomplished_writing_goal, date
    ):
        self.session_id = session_id
        self.user_id = user_id
        self.journ_text = journ_text
        self.words_per_minute = words_per_minute
        self.accomplished_writing_goal = accomplished_writing_goal
        self.date = date


class JournalingShell(cmd.Cmd):
    intro_string_1 = "Welcome to Journ, type help or ? to list commands\n"
    intro_string_2 = "Type 'journ' to start\n"

    intro = intro_string_1 + intro_string_2
    prompt = "(journ) "
    writing_goal = 0
    name = None

    def login():
        "Register and Login"
        print("Welcome to journ!")
        print("The terminal-based journaling program\n")

        def confirm_login():
            def login():
                """Ask user for user name, check it against database"""
                user_name = input("What is your user name? ")
                user_data = cursor.execute(
                    """SELECT user_id, password, writing_goal FROM
                   user_info WHERE user_id = ?""",
                    [user_name],
                )

                user_data_grab = user_data.fetchone()
                
                if user_data_grab == None:
                    print("No user by that name, please try again or set up user name")
                    confirm_login()
                if user_data_grab != None:
                    password_actual = user_data_grab[1]
                else:
                    password_actual = ""

                password_attempt = input("What is your password? ")
                if password_actual == password_attempt:
                    User.user_id = user_name
                    User.writing_goal = user_data_grab[2]
                else:
                    print("invalid password")
                    login()
                return print("logged in")

            def register():
                user_name = input("Choose your username ")
                user_test =  cursor.execute(
                        """SELECT user_id FROM user_info WHERE user_id =?""",(user_name,)
                )
                try:
                    cursor.fetchall()[0]
                    print("Name Exists")
                    register()
                except:
                    pass
                password = input("Choose your password, if you don't want to have a password, leave blank ")
                writing_goal = input(
                    "Write your daily writing goal (Using digits only) "
                )
                confirm_user = input(f"Are you sure your want your user name to be {user_name}? (y/n) ")
                if confirm_user.lower() == "n":
                    register()
                else:
                    cursor.execute(
                        "INSERT INTO user_info VALUES (?, ? , ?)",
                        [user_name, password, int(writing_goal)],
                    )

                conn.commit()
                print("Now log in to the system")
                login()

            has_registered = input("Have you set up a user name and password?(y/n) ")

            if has_registered.lower() == "y":
                login()

            elif has_registered.lower() == "n":
                register()
            else:
                print("input has to be either y or no")
                confirm_login()

        confirm_login()

    def do_journ(self, line):
        "Starts the Journalling interface"

        start_time = datetime.now()
        filename = date.today()
        file_prefix = f"{filename.month}{filename.day}{filename.year}"
        file_string = f"{file_prefix}.txt"
        JournalingShell.clear()
        editor = getenv("EDITOR", "nano")

        if not path.isfile(file_string):
            directory = getcwd()
            for filename in listdir(directory):
                if filename.endswith(".txt"):
                    file_path = path.join(directory, filename)
                    remove(file_path)
        try:
            cursor.execute(
                """SELECT journal_text FROM journal_session WHERE session_id=?""", [file_prefix],
            )
            journ_data = cursor.fetchall()[0][0]
        except:
            journ_data = ""

        with open (file_string, "w") as temp_file:
            temp_file.write(journ_data)

        subprocess.run([editor,file_string])

        with open (file_string, "r") as temp_file:
            edited_content = temp_file.read()

        contents = edited_content
        remove(file_string)
        journal_length = len(contents.split())

        if journal_length >= User.writing_goal :
            print(f"You've typed {journal_length} words. This is over your goal of {User.writing_goal} words!")

        else:
            print(f"You've typed {journal_length} words. This is under your goal of {User.writing_goal} words")
        
        if journal_length >= User.writing_goal:
            accomplished_goal = True
        else:
            accomplished_goal = False
            
        end_time = datetime.now()

        elapsed_time = end_time - start_time

        in_seconds = elapsed_time.total_seconds()
        in_minutes = in_seconds / 60
        time_string = str(elapsed_time)

        parsed_time = time_string.split(":")
        print(
            f"You've journalled for {parsed_time[0]} hour(s), {parsed_time[1]} minute(s), and {parsed_time[2][:2]} seconds"
        )
        journ_wpm = round(journal_length / in_minutes, 1)
        currentSession = JournalSession
        currentSession.session_id = file_prefix
        currentSession.user_id = User.user_id
        currentSession.journ_text = contents
        currentSession.words_per_minute = journ_wpm
        currentSession.date = str(end_time)
        currentSession.accomplished_writing_goal = accomplished_goal

        try:
            cursor.execute(
                "INSERT INTO journal_session VALUES (?, ? , ?, ?, ?, ?)",
                [
                    currentSession.session_id,
                    currentSession.user_id,
                    currentSession.journ_text,
                    currentSession.words_per_minute,
                    currentSession.date,
                    currentSession.accomplished_writing_goal,
                ],
            )
        except:
            cursor.execute(
                "UPDATE journal_session SET journal_text=?, accomplished_writing_goal=? WHERE session_id=?", (currentSession.journ_text, currentSession.accomplished_writing_goal, currentSession.session_id)
            )
        conn.commit()

    def do_streak_details(self, line):
        print(line)
        raise NotImplementedError

    def do_fetch_user_data(self, line):
        "Grabs all database data for the logged in user"
        cursor.execute("SELECT * FROM user_info Where user_id=?", (User.user_id,))
        conn.commit()
        print(cursor.fetchall())
        print(f"Grabbing data for user -> {User.user_id}. \n")
        cursor.execute("SELECT * FROM journal_session WHERE user_id=?", (User.user_id,))
        print(cursor.fetchall())
        conn.commit()

    def do_test(self, line):
        "Check DB Status, should be two tables (DELETE BEFORE FINAL RELEASE"
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        print(cursor.fetchall())
        conn.commit()

    def do_change_writing_goal(self, args):
        "Change your writing goal"
        confirm = input("Do you want to change your wirting goal (y/n) ")
        if confirm.lower() == "n":
            return
        elif confirm.lower() == "y":
            change = input("New word goal -> ")
            try:
                change = int(change)
            except:
                print("input must be a round number")
                change = "ERRROR"

            if change == "ERROR":
                change_writing_goal()
            else:
                User.writing_goal = change

                cursor.execute(
                    "UPDATE user_info SET writing_goal=? WHERE user_id=?", (User.writing_goal, User.user_id))
                conn.commit()

    def do_todays_journ(self, line):
        cursor.execute(
                """SELECT journal_text FROM journal_session"""
        )
        current_text = cursor.fetchall()[-1][0]
        text_length = len(current_text.split())
        print(f"Your current word count for today is {text_length} and your goal word count it {User.writing_goal}.")

    def clear():
        if name == "nt":
            _ = system("cls")

        else:
            _ = system("clear")

    def do_exit(self, line):
        "Exits System"
        return self.__do_EOF__(line)

    def __do_EOF__(self, line):
        return True


if __name__ == "__main__":
    JournalingShell.clear()
    JournalingShell.login()
    JournalingShell.clear()
    JournalingShell().cmdloop()
    conn.close()
