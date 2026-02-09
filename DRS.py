import tkinter
import cv2
import PIL.Image, PIL.ImageTk
from functools import partial
import threading
import time
import imutils


stream = cv2.VideoCapture("video.mp4")
flag = True
def play(speed):
    global flag
    print(f"You clicked on play. Speed is {speed}")
    
    frame1 = stream.get(cv2.CAP_PROP_POS_FRAMES)
    stream.set(cv2.CAP_PROP_POS_FRAMES, frame1 + speed)
        
    grabbed, frame = stream.read()
    frame = imutils.resize(frame, width=SET_WIDTH, height=SET_HEIGHT)
    frame = PIL.ImageTk.PhotoImage(image= PIL.Image.fromarray(frame))
    canvas.image = frame 
    canvas.create_image(0,0,image=frame, anchor=tkinter.NW)
    if flag:
        canvas.create_text(140,20 ,fill="red", font= "Times 20 italic bold", text="DECISION PENDING")
    flag = not flag
  
    
def pending(decision):
    frame = cv2.cvtColor(cv2.imread("decisionpending.jpg"),cv2.COLOR_BGR2RGB)
    frame = imutils.resize(frame, width=SET_WIDTH, height=SET_HEIGHT)
    frame =PIL.ImageTk.PhotoImage(image=PIL.Image.fromarray(frame))
    canvas.image = frame
    canvas.create_image(0,0,image=frame, anchor=tkinter.NW)
    time.sleep(1.75)
    
    if decision == 'out':
        decisionImg= "out.jpg"
    else:
        decisionImg = "notout.jpg"
        
    frame = cv2.cvtColor(cv2.imread(decisionImg),cv2.COLOR_BGR2RGB)
    frame = imutils.resize(frame, width=SET_WIDTH, height=SET_HEIGHT)
    frame =PIL.ImageTk.PhotoImage(image=PIL.Image.fromarray(frame))
    canvas.image = frame
    canvas.create_image(0,0,image=frame, anchor=tkinter.NW)
    time.sleep(1) 
   
    
def out():
    thread = threading.Thread(target=pending, args=("out",))
    thread.daemon = True
    thread.start()
    print("OUT")

def not_out():
    thread = threading.Thread(target=pending, args=("not out",))
    thread.daemon = True
    thread.start()
    print("NOT OUT")

    
    

# width and height of our main screen
SET_WIDTH=750
SET_HEIGHT=558

# using tkinter gui 
window = tkinter.Tk()
window.title("Python presents Third umpire DECISION REVIEW SYSTEM")
cv_img = cv2.cvtColor(cv2.imread("presents.jpg"), cv2.COLOR_BGR2RGB)
canvas = tkinter.Canvas(window,width=SET_WIDTH, height=SET_HEIGHT)
photo = PIL.ImageTk.PhotoImage(image=PIL.Image.fromarray(cv_img))
image_on_canvas = canvas.create_image(0,0,ancho=tkinter.NW, image=photo)
canvas.pack()

#buttons to control playback

btn = tkinter.Button(window, text="<< Previous (Fast)", width=50, command=partial(play,-25))
btn.pack()

btn = tkinter.Button(window, text="<< Previous (Slow)", width=50, command=partial(play,-2))
btn.pack()

btn = tkinter.Button(window, text="Forward (Fast) >>", width=50, command=partial(play,25))
btn.pack()

btn = tkinter.Button(window, text="Forward (Slow) >>", width=50, command=partial(play,2))
btn.pack()

btn = tkinter.Button(window, text=" OUT", width=50, command=out)
btn.pack()

btn = tkinter.Button(window, text=" NOT OUT ", width=50, command=not_out)
btn.pack()

window.mainloop()