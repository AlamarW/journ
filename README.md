## Why journ?
journ is a terminal-based journaling app meant to keep you in your terminal. As I've progressed in my development journey, I realized that developers want to stay in their editor/IDE of choice as long as possible. journ is meant to work with your default editor of choice so that you can go from journaling to development all from the ease of the terminal. All while helping you stay accountabile with a daily word goal and streak tracker.

## About the Project
journ started as a project to mimic much of the functionality of the website 750words.com but to make the data local for the users instead of in a cloud. It started to feel weird to me with how much personal stuff I was journaling with on a site with a backend that was not in my control.

Since conception of the project, I've deviated a bit from the clone of 750words.com goal and am dedicating myself to a "fully featured" journaling app in the terminal. The core of journ is that I don't want to take your default text editor from you. People who like to do things in their terminal have their editor of choice (I use neovim btw) and so journ defaults to whatever you have it set up as.

It's helpful to have a word counter in your text editor of choice, but journ will take care of that for you if not (just not as elegantly)


The Completion of below will make journ official v1
### To Do List

- [X] Fully implement daily tmp file for editing
- [x] User login
  - [x] Prevent journaling to anyone logged out
  - [x] Journal Session logging
  - [x] User goals fully implemented
  - [x] Storage of data based on User Login
  - [x] sqlite database uses stored user idea
    - [x] User can update their goals
- [] Journaling streak
- [x] Implement default to user defined text editor
- [x] Make password optional
- [x] Add current journ data (word count mostly)

### Bug List
- [x] Changing login system created error when user says they've logged in if db is empty
- [x] System allows for overwriting of user names
- [] Current implementation creates difficult loop if register process starts and user isn't sure they want the selected login, not sure how to fix right now. Will have to replace the recursive calls with while loops.
- [x] journal sessions are not currently tied to user/any user can access any other users' current journ
