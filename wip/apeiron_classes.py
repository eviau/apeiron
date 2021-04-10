# une classe pour le fd et interagir avec le système.
# contient le rendering?

# une classe pour les éditeurs. dans le __init__ il y a un attribut
# qui contient le type d'éditeur qu'on a fait

# =======================================================

# 27 oct: stop at def scrol(self), ligne 142. je n'arrive pas à décider où placer cette fonction...


from typing import List

import errno
import fcntl
import os
import string
import struct
import sys
import termios
import time

APEIRON_QUIT_TIMES = 3

MODE_EDIT = 0
MODE_DIR = 1
MODE_FOCUS = 2

DEFAULT_STATUS_MSG = " APEIRON : Ctrl-S pour sauvegarder | Ctrl-Q pour quitter"

TEMP_FOLDER = "temp_saved_files/"

TEMP_FILENAME = "temp"

PATH_AGENDA = "agenda/"


APEIRON_VERSION = "0.0.1"

BACKSPACE = "\x7f"

ARROW_LEFT = 1000
ARROW_RIGHT = 1001
ARROW_UP = 1002
ARROW_DOWN = 1003
PAGE_UP = 1004
PAGE_DOWN = 1005
DEL_KEY = 1006

ENTER = 13

ESC = 27

TEMP_FOLDER = "temp_saved_files/"

TEMP_FILENAME = "temp"

logfile = None

PATH_AGENDA = "agenda/"



class Content():
    def __init__(self, mode=MODE_EDIT,dir=list()):
        self.cx = 0
        self.cy = 0
        self.numrows = 0
        # could merge these three
        self.row = list()
        self.dir = dir
        self.focus_on = ""
        # not sure about rowoff and coloff - pense pas que ce soit
        # nécessaire de les avoir pour content()
        self.rowoff = 0
        self.coloff = 0
        # could make an if on the mode to
        # have the appropriate status msg from the start
        self.statusmsg = ""
        self.statusmsg_time = 0

        self.dirty = 0
        self.quit_times = APEIRON_QUIT_TIMES
        self.mode = mode

    def set_status_message(self, msg):
        self.statusmsg = msg
        self.statusmsg_time = time.time()
    
    def update_row(self, at):
        self.row[at].render = ""
        self.row[at].render = self.row[at].chars + "\0"
        self.row[at].rsize += 1
        self.row[at].size += 1        
    
    def insert_row(self, row: str, at: int):
        if at < 0 or at > self.numrows:
            return

        empty = ERow()
        self.row.insert(at, empty)
        self.row[at].rsize = len(row)
        self.row[at].size = len(row)
        self.row[at].chars = row

        self.update_row(at)

        self.numrows = self.numrows + 1
        self.dirty = self.dirty + 1

    def free_row(self, at: int):
        self.row[at].render = ''
        self.row[at].chars = ''
    
    def del_row(self):
        if self.cy < 0 or self.cy >= self.numrows:
            return
#        self.free_row(at)
        del self.row[self.cy]
        self.numrows -= 1
        self.dirty += 1

    def row_insert_char(self, c: str):
        at = self.cx
        if at < 0 or at > self.row[self.cy].size:
            at = self.row[self.cy].size
        self.row[self.cy].chars = self.row[self.cy].chars[:at] + \
            str(c) + self.row[self.cy].chars[at:]
        self.row[self.cy].size = self.row[self.cy].size + 1
        self.update_row(self.cy)
        self.dirty = self.dirty + 1

    def row_append_string(self, s):
        self.row[self.cy-1].chars += s
        self.row[self.cy-1].size += len(s)
        self.update_row(self.cy-1)
        self.dirty += 1

    def row_del_char(self, at):
        if at < 0 or at >= self.row[self.cy].size:
            return
        self.row[self.cy].size -= 1
        self.row[self.cy].rsize -= 1
        self.row[self.cy].chars = self.row[self.cy].chars[:at] + \
            self.row[self.cy].chars[at+1:]
        self.update_row(self.cy)
        self.dirty += 1
    
    def insert_char(self, c):
        if self.cy == self.numrows:
            self.insert_row("", 0)
        self.row_insert_char(c)
        self.cx = self.cx + 1
    
    def insert_new_line(self):
        row = self.row[self.cy]

        if self.cx == 0 or self.cx > row.size:
            self.insert_row("", self.cy)
        else:
            log(row.chars)
            log(self.cx)
            self.insert_row(row.chars[self.cx+1:], self.cy + 1)
            row = self.row[self.cy]
            row.chars = row.chars[:self.cx+1]
            row.size = self.cx
            row.chars += '\0'
            self.update_row(self.cy)
        self.cy += 1
        self.cx = 0
    
    def del_char(self):
        if self.cy == self.numrows:
            return
        if self.cx == 0 and self.cy == 0:
            return
        if self.cx > 0:
            self.row_del_char(self.cx-1)
            self.cx -= 1
        else:
            self.cx = self.row[self.cy - 1].size
            self.row_append_string(self.row[self.cy].chars)
            self.del_row()
            self.cy -= 1

class Buffer():
    def __init__(self, ln=0, b=""):
        self.b = b
        self.ln = ln

    def append(self, s, ln):
        self.b = self.b + s
        self.ln += ln

    def free(self):
        self.b = ""
        self.ln = 0

class ERow():
    def __init__(self, size=0, chars=''):
        self.size = size
        self.rsize = 0
        self.chars = chars
        self.render = ''

class Screen():
    def __init__(self, rows, cols):
        self.screenrows = rows - 2
        self.screencols = cols
        self.cx = 0
        self.cy = 0
        self.current_mode = MODE_EDIT
        self.dir = Content(dir=sorted(os.listdir(PATH_AGENDA)))
        self.focus = Content()
        self.edit = Content()
        self.rowoff = 0
        self.coloff = 0
        self.filename = ""
        self.fd = ""
        self.atexit = ""
        
    def enable_raw_mode(self):
        self.fd = sys.stdin.fileno()
        self.atexit = termios.tcgetattr(self.fd)
        new = termios.tcgetattr(self.fd)
        new[0] = new[0] & ~(termios.BRKINT | termios.ICRNL |
                            termios.INPCK | termios.ISTRIP | termios.IXON)
        new[1] = new[1] & ~(termios.OPOST)
        new[2] = new[2] | termios.CS8
        new[3] = new[3] & ~(termios.ECHO | termios.ICANON |
                            termios.IEXTEN | termios.ISIG)
        new[6][termios.VMIN] = 0
        new[6][termios.VTIME] = 1

        termios.tcsetattr(self.fd, termios.TCSAFLUSH, new)

    def disable_raw_mode(self):
        termios.tcsetattr(self.fd, termios.TCSAFLUSH, self.atexit)

    def pick_content(self):
        if self.current_mode == MODE_DIR:
            return self.dir
        elif self.current_mode == MODE_EDIT:
            return self.edit
        elif self.current_mode == MODE_FOCUS:
            return self.focus

    def change_mode(self):
        self.current_mode = (self.current_mode + 1) % 3
        if self.current_mode == MODE_DIR:
            os.system(
                "wmctrl -r 'edith@hal: ~/dev/gh/apeiron/wip' -e 0,50,50,786,527")
            self.dir.set_status_message("Mode RÉPERTOIRE")
        elif self.current_mode == MODE_FOCUS:
            os.system(
                "wmctrl -r ' ~/dev/gh/apeiron/wip' -e 0,50,50,800,50")
            os.system("wmctrl -r ' ~/dev/gh/apeiron/wip' -b add,above")
            self.focus.set_status_message("Mode FOCUS")
            log('self.edit.dir[self.edit.cy]')
            log(self.edit.dir)
            log(self.edit.cy)
            if self.edit.row[self.edit.cy].size == 0:
                self.focus.focus_on = "Aucune tâche en cours."
            else:
                self.focus.focus_on = self.edit.row[self.edit.cy].render
        elif self.current_mode == MODE_EDIT:
            os.system(
                "wmctrl -r ' ~/dev/gh/apeiron/wip' -b remove,above")
            os.system(
                "wmctrl -r ' ~/dev/gh/apeiron/wip' -e 0,50,50,786,527")
            self.edit.set_status_message(DEFAULT_STATUS_MSG)

    def scroll(self):
        if self.current_mode == MODE_DIR:
            self.cx = self.dir.cx
            self.cy = self.dir.cy
        elif self.current_mode == MODE_EDIT:
            self.cx = self.edit.cx
            self.cy = self.edit.cy
        elif self.current_mode == MODE_FOCUS:
            self.cx = self.focus.cx
            self.cy = self.focus.cy
        if self.cy < self.rowoff:
            self.rowoff = self.cy
        if self.cy >= self.rowoff + self.screenrows:
            self.rowoff = self.cy - self.screenrows + 1
        if self.cx < self.coloff:
            self.coloff = self.cx
        if self.cx >= self.coloff + self.screencols:
            self.coloff = self.cx - self.screencols + 1

    def prompt(self, prompt):
        buf = ""
        buflen = 0
        while True:
            current_content = self.pick_content()
            current_content.set_status_message(prompt + buf + '\0')
            self.refresh()
            c = read_key()
            while c == '':
                c = read_key()
            if c == DEL_KEY or c == BACKSPACE:
                if buflen > 0:
                    buflen -= 1
                    buf = buf[:buflen]
            elif c == ESC:
                current_content.set_status_message("")
                return
            elif c == ENTER:
                if buflen != 0:
                    current_content.set_status_message("")
                    return buf[:buflen-1]
            elif c in string.printable and ord(c) < 128:
                buf += c
                buflen += 1
    
    def move_cursor(self, key):
        e = self.pick_content()
        row = ERow()
        row.chars = e.row[e.cy].chars if (e.cy < e.numrows) else ""
        row.size = e.row[e.cy].size if e.cy < e.numrows else 0

        if key == ARROW_LEFT:
            if (e.cx != 0):
                e.cx = e.cx - 1
            elif e.cy > 0:
                e.cy = e.cy - 1
                e.cx = e.row[e.cy].size
        elif key == ARROW_RIGHT:
            if row.size > 0 and (e.cx < row.size):
                e.cx = e.cx + 1
            elif row.size > 0 and e.cx == row.size:
                e.cy = e.cy + 1
                e.cx = 0
        elif key == ARROW_UP:
            if self.current_mode == MODE_EDIT:
                if (e.cy != 0):
                    e.cy = e.cy - 1
            elif self.current_mode == MODE_FOCUS:    
                if self.focus.cy > 0:
                    self.focus.cy = self.focus.cy - 1
        elif key == ARROW_DOWN:
            log("e.cx, e.cy : ", e.cx, e.cy)
            if self.current_mode == MODE_EDIT:
                if (e.cy < e.numrows):
                    e.cy = e.cy + 1
            elif self.current_mode == MODE_DIR:
                if self.dir.cy < len(self.dir.dir):
                    self.dir.cy = self.dir.cy + 1
        row.chars = e.row[e.cy].chars if (e.cy < e.numrows) else ""
        row.size = e.row[e.cy].size if e.cy < e.numrows else 0
        rowlen = 0 if row.size <= 0 else row.size
        if e.cx > rowlen:
            e.cx = rowlen

    def refresh(self):
        buff = Buffer()
        self.scroll()
        buff.append('\x1b[?25l', 6)
        buff.append('\x1b[H', 3)
        
        self.append_mode(buff)
        self.draw_message_bar(buff)
        
        if self.current_mode == MODE_EDIT or self.current_mode == MODE_DIR:
            buf = "\x1b[" + str(self.cy + 1 - self.rowoff) + ";" + \
                str(self.cx + 1 - self.coloff) + "H"   
            bufsize = sys.getsizeof(buf)
            buff.append(buf,bufsize)
        
        buff.append('\x1b[?25h', 6)

        temp = ""
        for elem in (buff.b):
            temp = temp + elem
        # 4 avril 2021 - 10 avril 2021 : move the Config class to the Screen class
        os.write(self.fd, bytes(temp, encoding="utf-8"))
        buff.free()
    
    def append_mode(self,buff):
        if self.current_mode == MODE_DIR:
            nb_elem = 0
            for f in self.dir.dir:
                buff.append(f, len(f))
                buff.append("\x1b[K", 3)
                buff.append("\r\n", 2)
                nb_elem += 1
                if nb_elem == self.screenrows:
                    break
        
        elif self.current_mode == MODE_EDIT:

            for y in range(self.screenrows):
                filerow = y + self.rowoff
                if filerow >= self.edit.numrows:
                    if self.edit.numrows == 0 and y == self.screenrows/3:
                        welcome = "Bienvenue sur Apeiron, version " + APEIRON_VERSION
                        welcomelen = sys.getsizeof(welcome)
                        if welcomelen > self.screencols:
                            welcomelen = self.screencols
                        buff.append(welcome, welcomelen)
                    else:
                        buff.append("~", 1)
                else:
                    ln = self.edit.row[filerow].rsize - self.coloff
                    if ln < 0:
                        ln = 0
                    if ln > self.screencols:
                        ln = self.screencols
                    buff.append(self.edit.row[filerow].render, ln)
                buff.append("\x1b[K", 3)
                buff.append('\r\n', 2)
            self.draw_status_bar(buff)
        
        elif self.current_mode == MODE_FOCUS:
            buff.append(self.focus.focus_on, len(self.focus.focus_on)-1)
            buff.append("\x1b[K", 3)
            buff.append("\r\n", 2)
            buff.append("\x1b[K", 3)
            buff.append("\r\n", 2)
            self.draw_status_bar(buff)
  
    def draw_status_bar(self,buff):
        buff.append("\x1b[7m", 4)
        status = self.filename
        if self.edit.dirty > 0:
            status = status + " (modified)"

        if self.current_mode == MODE_FOCUS:
            status = " APEIRON : appuyez sur Ctrl-D pour revenir en mode éditeur."

        ln = len(status)
        
        if ln > self.screencols:
            ln = self.screencols
        buff.append(status, ln)
        while ln < self.screencols:
            buff.append(" ", 1)
            ln = ln + 1
        buff.append("\x1b[m", 3)
        buff.append("\r\n", 2)

    def draw_message_bar(self,buff):
        buff.append("\x1b[K", 3)
        msgln = len(self.pick_content().statusmsg)
        if msgln > self.screencols:
            msgln = self.screencols
        if msgln and time.time() - self.pick_content().statusmsg_time < 5:
            buff.append(self.pick_content().statusmsg, msgln)

class Kernel():
    def __init__(self,rows,cols):
        self.screen = Screen(rows,cols)
        self.start_time = time.time()

    def autosave(self):
        current = str(time.time())
        current_content = self.screen.pick_content()
        with open(TEMP_FOLDER + TEMP_FILENAME + "_" + current + ".txt", 'w+') as f:
            for r in current_content.row:
                f.write(str(r.chars[:r.size-2]))
                f.write(str('\n'))
            if self.screen.current_mode == MODE_EDIT:
                current_content.set_status_message(
                    "Sauvegarde temporaire effectuée.")
            f.close()

    def delete_temp_files(self):
        list_temp_dir = os.listdir(TEMP_FOLDER)
        for file in list_temp_dir:
            timed = file[len(TEMP_FILENAME)+1:-4]
            if float(timed) > self.start_time:
                os.remove(TEMP_FOLDER + file)
    
    def save(self):
        current_content = self.screen.edit
        if self.screen.filename == "":
            self.filename = self.screen.prompt(
                "(ESC pour annuler) Enregistrer sous : ")
            if self.filename == "":
                current_content.set_status_message("Sauvegarde annulée.")
                return
        with open(PATH_AGENDA + self.filename, 'w+') as f:
            for r in current_content.row:
                f.write(str(r.chars[:r.size-2]))
                f.write(str('\n'))
        current_content.set_status_message("Sauvegarde effectuée.")
        f.close()
        current_content.dirty = 0
        self.delete_temp_files()

    def find(self):
        current_content = self.screen.edit
        query = self.prompt("(ESC pour annuler) Recherche: ")
        if query == "":
            return
        for i in range(current_content.numrows):
            match = query in current_content.row[i].render
            if match:
                self.screen.cy = i
                self.screen.cx = self.row[i].render.find(query)
                self.screen.rowoff = current_content.numrows
                break

    def open(self, filename):
        self.filename = filename
        self.screen.edit.numrows = 0
        if os.path.exists(PATH_AGENDA + filename):
            with open(PATH_AGENDA + filename, 'r') as fichier:
                row = fichier.readline()
                while (len(row) >0 and row != 'EOF'):
                    self.screen.edit.insert_row(row[:len(row)-1], self.screen.edit.numrows) 
                    row = fichier.readline()
            fichier.close()
        self.screen.edit.dirty = 0

    def process_keypress(self):
        c = read_key()
        log("a key is pressed!")
        while c == '':
            log("am i in the while? yes!")
            c = read_key()
        log("key pressed: ")
        log(c)
        if c == ctrl('d'):
            self.screen.change_mode()
        if self.screen.current_mode == MODE_DIR:
            if (c == ARROW_UP or c == ARROW_DOWN):
                self.screen.move_cursor(c)
            elif c == ENTER:
                self.save()
                log('screen.dir.dir')
                log(self.screen.dir.dir)
                self.open(self.screen.dir.dir[self.screen.dir.cy])
                self.current_mode = MODE_EDIT

        elif self.screen.current_mode == MODE_EDIT:
            if c == ctrl('q'):
                if self.screen.edit.dirty > 0 and self.screen.edit.quit_times > 0:
                    errorquit = "Attention! Le fichier comporte des changements qui n'ont pas été sauvegardés." +  \
                                "Appuyez sur Ctrl-Q " + \
                                str(self.screen.edit.quit_times) + \
                        " fois pour quitter tout de même."
                    self.screen.edit.set_status_message(errorquit)
                    self.screen.edit.quit_times -= 1
                    return
                sys.stdout.write('\x1b[2J')
                sys.stdout.write('\x1b[H')
                self.screen.disable_raw_mode()
                sys.exit()
            elif c == ctrl('s'):
                self.save()
            elif c == ctrl('f'):
                self.find()
            elif c == ENTER:
                log("enter key pressed? yes!")
                self.screen.edit.insert_new_line()
            elif c == BACKSPACE or c == DEL_KEY:
                self.screen.edit.del_char()
            elif (c == PAGE_UP or c == PAGE_DOWN):
                if c == PAGE_UP:
                    self.screen.edit.cy = self.screen.rowoff
                elif c == PAGE_DOWN:
                    self.screen.edit.cy = self.screen.rowoff + self.screen.screenrows - 1
                    if self.screen.edit.cy > self.screen.edit.numrows:
                        self.screen.edit.cy = self.screen.edit.numrows
                times = self.screen.screenrows
                while (times):
                    self.screen.move_cursor(ARROW_UP if PAGE_UP else PAGE_DOWN)
                    times -= times
            elif (c == ARROW_DOWN or c == ARROW_UP or c == ARROW_LEFT or c == ARROW_RIGHT):
                self.screen.move_cursor(c)
            else:
                self.screen.edit.insert_char(c)
            self.screen.edit.quit_times = APEIRON_QUIT_TIMES

def read_key():
    try:
        c = sys.stdin.read(1)
    except OSError as err:
        if err.errno == errno.EAGAIN:
            print("ERROR" + err.errno)
            sys.stdout.write('\x1b[2J')
            sys.stdout.write('\x1b[H')
            sys.exit()
        else:
            raise

    if c == "\x1b":
        try:
            seq = sys.stdin.read(2)
            if seq[0] == '[':
                temp = seq[1]
                if (ord(temp) >= ord('0') and ord(temp) <= ord('9')):
                    if seq[2] == '~':
                        if temp == '5':
                            return PAGE_UP
                        elif temp == '6':
                            return PAGE_DOWN
                        elif temp == '3':
                            return DEL_KEY
                elif temp == 'A':
                    return ARROW_UP
                elif temp == 'B':
                    return ARROW_DOWN
                elif temp == 'C':
                    log("reading the ARROW_RIGHT")
                    return ARROW_RIGHT
                elif temp == 'D':
                    return ARROW_LEFT
        except (OSError, IndexError) as err:
            return 0x1b
        return 0x1b
    log("just before this")
    log(c)
    if c == "\r":
        return ENTER
    return c

def get_window_size():
    return (struct.unpack('hh', fcntl.ioctl(sys.stdout.fileno(), termios.TIOCGWINSZ, '1234')))


def log(*args):
    print(*args, file=logfile)

def ctrl(key):
        return chr(ord(key) & 0x1f)

if __name__ == "__main__":
    try:
        logfile = open("log.txt", 'a')
        log("This is a new session!")
        # ## Config class is archived into Screen class
        # conf = Config()
        # conf.enable_raw_mode()
        hw = get_window_size()
        krnl = Kernel(hw[0],hw[1])
        krnl.screen.enable_raw_mode()
     
        if len(sys.argv) >= 2:
            print(sys.argv[1])
            krnl.screen.filename = sys.argv[1]
            krnl.open(sys.argv[1])

        krnl.screen.edit.set_status_message(
            DEFAULT_STATUS_MSG)

        while True:
            krnl.screen.refresh()
            krnl.process_keypress()
            krnl.autosave()
        
    except:
        krnl.screen.disable_raw_mode()
        raise
