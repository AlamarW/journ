import cmd
import sqlite3
from datetime import datetime, date, timedelta
from os import system, name, getenv, remove, path, listdir, getcwd, makedirs
import subprocess
import tempfile
import time

home_dir = path.expanduser("~")
journal_filepath = path.join(home_dir,".journ", "journal.db")
makedirs(path.dirname(journal_filepath), exist_ok=True)

conn = sqlite3.connect(journal_filepath)
cursor = conn.cursor()
cursor.execute(
    """CREATE TABLE IF NOT EXISTS user_info (
                user_id text,
                password text,
                writing_goal integer,
                streak integer,
                streak_added
                )"""
)

conn.commit()

cursor.execute(
    """CREATE TABLE IF NOT EXISTS journal_session (
               session_id text PRIMARY KEY,
               session_name text,
               user_id text,
               journal_text blob,
               words_per_minute real,
               date text,
               accomplished_writing_goal
               )"""
)

conn.commit()


class User:
    def __init__(self, user_id, password, writing_goal, streak, streak_added):
        self.user_id = user_id
        self.password = password
        self.writing_goal = writing_goal
        self.streak = streak
        self.streak_added = streak_added

    def register(self):
        print(self.user_id)
        print(self.password)

class JournalSession:
    def __init__(
        self, session_id, session_name, user_id, journ_text, words_per_minute, accomplished_writing_goal, date
    ):
        self.session_id = session_id
        self.session_name = session_name
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

    def main_login():
        """Register and Login"""
        print("Welcome to journ!")
        print("The terminal-based journaling program\n")

        def confirm_login():

            def login():
                """Ask user for user name, check it against database"""
                loop = True
                while loop:
                    user_name = input("What is your user name? ")
                    user_data = cursor.execute(
                        """SELECT user_id, password, writing_goal, streak, streak_added FROM
                       user_info WHERE user_id = ?""",
                        [user_name],
                    )

                    user_data_grab = user_data.fetchone()
                    
                    if user_data_grab == None:
                        print("No user by that name, please try again or set up user name")
                        continue
                    if user_data_grab != None:
                        password_actual = user_data_grab[1]
                    else:
                        password_actual = ""

                    password_attempt = input("What is your password? ")
                    if password_actual == password_attempt:
                        User.user_id = user_name
                        User.writing_goal = user_data_grab[2]
                        User.streak = user_data_grab[3]
                        User.streak_added = user_data_grab[4]
                    else:
                        print("invalid password")
                        continue
                    return print("logged in")

            def register():
                while True:
                    user_name = input("Choose your username ")
                    user_test =  cursor.execute(
                            """SELECT user_id FROM user_info WHERE user_id =?""",(user_name,)
                    )
                    try:
                        cursor.fetchall()[0]
                        print("Name Exists")
                        continue
                    except:
                        pass
                    password = input("Choose your password, if you don't want to have a password, leave blank ")
                    writing_goal = input(
                        "Write your daily writing goal (Using digits only) "
                    )
                    confirm_user = input(f"Are you sure your want your user name to be {user_name}? (y/n) ")
                    if confirm_user.lower() == "n":
                        continue
                    else:
                        cursor.execute(
                            "INSERT INTO user_info VALUES (?, ? , ?, ?, ?)",
                            [user_name, password, int(writing_goal), 0, False],
                        )
                    conn.commit()
                    print("Now login with your credentials ")
                    login()
                    break
            loop = True
            while loop:
                has_registered = input("Have you set up a user name and password?(y/n) ")

                if has_registered.lower() == "y":
                    login()
                    loop = False
                    break

                elif has_registered.lower() == "n":
                    register()
                    loop = False
                    break
                else:
                    print("input has to be either y or no")
                    continue

        confirm_login()

    def do_journ(self, line):
        "Starts the Journalling interface"
        
        def streak_calc(today_date, currentSession):
            previous_day = today_date - timedelta(days=1)
            file_prefix = f"{previous_day.month}{previous_day.day}{previous_day.year}"

            cursor.execute(
                    """SELECT journal_text FROM journal_session WHERE session_name=? AND user_id=?""", [file_prefix, User.user_id],
            )

            try:
                content = cursor.fectchall()[0]
            except:
                content = False

            if content and currentSession.accomplished_writing_goal == True and User.streak_added == False:
                print("there was an entry for yesterday")
                User.streak +=1
                User.streak_added = True
                print(f"your current streak is {User.streak}")
            elif content and currentSession.accomplished_writing_goal == False:
                print("There was an entry for yesterday but you haven't finished your word goal today")
                print(f"Your current streak is {User.streak}, but will go to {User.streak + 1} when you finish your goal today")
            elif content == False and currentSession.accomplished_writing_goal == True and User.streak_added == False:
                User.streak += 1
                User.streak_added = True
                print(f"Your current streak is {User.streak}")
            else:
                print(f"Your current streak is {User.streak}")

        start_time = datetime.now()
        today_date = date.today()
        file_prefix = f"{today_date.month}{today_date.day}{today_date.year}"
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
                """SELECT journal_text FROM journal_session WHERE session_name=? AND user_id=?""", [file_prefix,User.user_id],
            )
            journ_data = cursor.fetchall()[0][0]
        except:
            journ_data = ""
            User.streak_added = False

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
        journ_wpm = round(journal_length / in_minutes, 1)
        print(
            f"You've journalled for {parsed_time[0]} hour(s), {parsed_time[1]} minute(s), and {parsed_time[2][:2]} seconds"
        )
        print(
            f"That's {journ_wpm} words per minute"
        )
        JournalSession.session_id = f"{file_prefix}_{User.user_id}"
        JournalSession.session_name = file_prefix
        JournalSession.user_id = User.user_id
        JournalSession.journ_text = contents
        JournalSession.words_per_minute = journ_wpm
        JournalSession.date = str(end_time)
        JournalSession.accomplished_writing_goal = accomplished_goal

        streak_calc(today_date, JournalSession)

        try:
            cursor.execute(
                "INSERT INTO journal_session VALUES (?, ?, ?, ?, ?, ?, ?)",
                [
                    JournalSession.session_id,
                    JournalSession.session_name,
                    JournalSession.user_id,
                    JournalSession.journ_text,
                    JournalSession.words_per_minute,
                    JournalSession.date,
                    JournalSession.accomplished_writing_goal,
                ],
            )
        except:
            cursor.execute(
                "UPDATE journal_session SET journal_text=?, accomplished_writing_goal=? WHERE session_name=? AND user_id=?", (JournalSession.journ_text, JournalSession.accomplished_writing_goal, JournalSession.session_name,User.user_id)
            )
        conn.commit()

        try:
            cursor.execute(
                "UPDATE user_info SET streak=?, streak_added=? WHERE user_id=?", (User.streak, User.streak_added, User.user_id,) 
            )
        except:
            print("This is causing problems")
        conn.commit()
        
    def do_streak_details(self, line):
        "Pulls your current streak status"
        print(f"Your streak is currently {User.streak} days")

    def do_fetch_user_data(self, line):
        "Grabs all database data for the logged in user"
        cursor.execute("SELECT * FROM user_info Where user_id=?", (User.user_id,))
        conn.commit()
        print(cursor.fetchall())
        print(f"Grabbing data for user -> {User.user_id}. \n")
        cursor.execute("SELECT * FROM journal_session WHERE user_id=?", (User.user_id,))
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

    def do_last_journ(self, line):
        "Pulls the word count of your last journalling session (will be either from previous days, or from current day)"
        cursor.execute(
                """SELECT journal_text FROM journal_session WHERE user_id=?""", [User.user_id]
        )
        try:
            current_text = cursor.fetchall()[-1][0]
            text_length = len(current_text.split())
        except:
            text_length = 0
        print(f"Your current word count for today is {text_length} and your goal word count it {User.writing_goal}.")

    def do_change_password(self, line):
        while True:
            confirm_pass = input("Do you want to change your password? (y/n) ")
            if confirm_pass.lower() == "n":
                break
            elif confirm_pass.lower() == "y":

                change = input("New password -> ")
                confirm_change = input("Please put in password again -> ")
                if change == confirm_change:
                    cursor.execute(
                            "UPDATE user_info SET password=? WHERE user_id=?", (change, User.user_id)
                    )
                    conn.commit()
                else:
                    print("error, try again")
                    continue

                print("Changing password")
                break
            else:
                print("input must be y or n")
                continue


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

def main():
    JournalingShell.clear()
    JournalingShell.main_login()
    JournalingShell.clear()
    JournalingShell().cmdloop()
    conn.close()

if __name__ == "__main__":
    main()
