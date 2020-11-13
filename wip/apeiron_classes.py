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


class Config():
    def __init__(self):
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


class Content():
    def __init__(self, mode=MODE_EDIT):
        self.cx = 0
        self.cy = 0
        self.numrows = 0
        # could merge these three
        self.row = list()
        self.dir = list()
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
        self.render = '

class Screen():
    def __init__(self, rows, cols):
        self.screenrows = rows - 2
        self.screencols = cols
        self.cx = 0
        self.cy = 0
        self.current_mode = MODE_DIR
        self.dir = Content()
        self.focus = Content()
        self.edit = Content()
        self.rowoff = 0
        self.coloff = 0
        self.filename = ""


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
                "wmctrl -r ' ~/dev/perso/apeiron' -e 0,50,50,786,527")
            self.dir.set_status_message("Mode RÉPERTOIRE")
        elif self.current_mode == MODE_FOCUS:
            os.system(
                "wmctrl -r ' ~/dev/perso/apeiron' -e 0,50,50,800,50")
            os.system("wmctrl -r ' ~/dev/perso/apeiron' -b add,above")
            self.focus.set_status_message("Mode FOCUS")
            if len(self.focus.row[self.focus.cy].chars) == 0:
                self.focus.focus_on = "Aucune tâche en cours."
            else:
                self.focus.focus_on = self.focus.row[self.focus.cy].render
        elif self.current_mode == MODE_EDIT:
            os.system(
                "wmctrl -r ' ~/dev/perso/apeiron' -b remove,above")
            os.system(
                "wmctrl -r ' ~/dev/perso/apeiron' -e 0,50,50,786,527")
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
            c = Keyboard.read_key()
            while c == '':
                c = Keyboard.read_key()
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
        e = self.edit
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
            if e.mode_editor == 0:
                if (e.cy != 0):
                    e.cy = e.cy - 1
            elif e.mode_editor == 1:    
                if e.dir_cy > 0:
                    e.dir_cy = e.dir_cy - 1
        elif key == ARROW_DOWN:
            log("e.cx, e.cy : ", e.cx, e.cy)
            if e.mode_editor == 0:
                if (e.cy < e.numrows):
                    e.cy = e.cy + 1
            elif e.mode_editor == 1:
                if e.dir_cy < len(e.dir):
                    e.dir_cy = e.dir_cy + 1
        row.chars = e.row[e.cy].chars if (e.cy < e.numrows) else ""
        row.size = e.row[e.cy].size if e.cy < e.numrows else 0
        rowlen = 0 if row.size <= 0 else row.size
        if e.cx > rowlen:
            e.cx = rowlen

    def refresh(self):
        pass


class Kernel():
    def __init__(self):
        self.screen = Screen()
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
            timed = file(len(TEMP_FILENAME)+1: -4)
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
                self.rowoff = current_content.numrows
                break

    def open(self, filename):
        self.filename = filename
        self.screen.edit.numrows = 0
        if os.path.exists(PATH_AGENDA + filename):
            with open(PATH_AGENDA + filename, 'r') as fichier:
                row = fichier.readline()
                while (len(row) >0 and row != 'EOF'):
                    self.screen.edit.insert_row(row[:len(row)-1], self.screen.edit.numrows) 
                    row = readline()
            fichier.close()
        self.screen.edit.dirty = 0


class Keyboard():
    @staticmethod
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
    

    # UPDATE THIS METHOD
    @staticmethod
    def process_keypress(e):
        c = Keyboard.read_key()
        log("a key is pressed!")
        while c == '':
            log("am i in the while? yes!")
            c = Keyboard.read_key()
        log("key pressed: ")
        log(c)
        if c == Keyboard.ctrl('d'):
            e.change_mode()
        if e.mode_editor == 1:
            if (c == ARROW_UP or c == ARROW_DOWN):
                Keyboard.move_cursor(c, e)
            elif c == ENTER:
                e.save()
                e.open(e.dir[e.dir_cy])
                e.mode_editor = 0

        elif e.mode_editor == 0:
            if c == Keyboard.ctrl('q'):
                if e.dirty > 0 and e.quit_times > 0:
                    errorquit = "Attention! Le fichier comporte des changements qui n'ont pas été sauvegardés." +  \
                                "Appuyez sur Ctrl-Q " + \
                                str(e.quit_times) + \
                        " fois pour quitter tout de même."
                    e.set_status_message(errorquit)
                    e.quit_times -= 1
                    return
                sys.stdout.write('\x1b[2J')
                sys.stdout.write('\x1b[H')
                Config.disableRawMode(e)
                sys.exit()
            elif c == Keyboard.ctrl('s'):
                e.save()
            elif c == Keyboard.ctrl('f'):
                e.find()
            elif c == ENTER:
                log("enter key pressed? yes!")
                e.insert_new_line()
            elif c == BACKSPACE or c == DEL_KEY:
                e.del_char()
            elif (c == PAGE_UP or c == PAGE_DOWN):
                if c == PAGE_UP:
                    e.cy = e.rowoff
                elif c == PAGE_DOWN:
                    e.cy = e.rowoff + e.screenrows - 1
                    if e.cy > e.numrows:
                        e.cy = e.numrows
                times = e.screenrows
                while (times):
                    Keyboard.move_cursor(ARROW_UP if PAGE_UP else PAGE_DOWN, e)
                    times -= times
            elif (c == ARROW_DOWN or c == ARROW_UP or c == ARROW_LEFT or c == ARROW_RIGHT):
                Keyboard.move_cursor(c, e)
            else:
                e.insert_char(c)
            e.quit_times = APEIRON_QUIT_TIMES



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
        conf = Config()
        conf.enable_raw_mode()
        hw = get_window_size()
        krnl = Kernel()
