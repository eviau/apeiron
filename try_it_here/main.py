# the original, https://viewsourcecode.org/snaptoken/kilo

# agenda:
# - 21 juillet 2020: stop at step 21
# - 13 août: stop at step 118
# 9 octobre: step 132
# 12 oct: step 138
# 18 oct: refactor

from typing import List

import errno
import fcntl
import os
import string
import struct
import sys
import termios
import time

APEIRON_VERSION = "0.0.1"
APEIRON_QUIT_TIMES = 3

DEFAULT_STATUS_MSG = " APEIRON : Ctrl-S pour sauvegarder | Ctrl-Q pour quitter"

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


def log(*args):
    print(*args, file=logfile)


class ERow():
    def __init__(self, size=0, chars=''):
        self.size = size
        self.rsize = 0
        self.chars = chars
        self.render = ''


class Config():
    @staticmethod
    def disableRawMode(e):
        termios.tcsetattr(e.fd, termios.TCSAFLUSH, e.atexit)

    @staticmethod
    def enableRawMode():
        fd = sys.stdin.fileno()
        atexit = termios.tcgetattr(fd)
        new = termios.tcgetattr(fd)
        new[0] = new[0] & ~(termios.BRKINT | termios.ICRNL |
                            termios.INPCK | termios.ISTRIP | termios.IXON)
        new[1] = new[1] & ~(termios.OPOST)
        new[2] = new[2] | termios.CS8
        new[3] = new[3] & ~(termios.ECHO | termios.ICANON |
                            termios.IEXTEN | termios.ISIG)
        new[6][termios.VMIN] = 0
        new[6][termios.VTIME] = 1

        termios.tcsetattr(fd, termios.TCSAFLUSH, new)

        return fd, atexit

    @staticmethod
    def getWindowSize():
        return (struct.unpack('hh', fcntl.ioctl(sys.stdout.fileno(), termios.TIOCGWINSZ, '1234')))


class Editor():
    def __init__(self, fd, atexit, rows, cols, numrows=0, filename=''):
        self.fd = fd
        self.atexit = atexit
        self.screenrows: int = rows - 2
        self.screencols: int = cols
        self.cx: int = 0
        self.cy: int = 0
        self.dir_cy = 0
        self.rx: int = 0
        self.numrows: int = numrows
        self.row: List[ERow] = list()
        self.rowoff: int = 0
        self.coloff: int = 0
        self.filename: str = filename
        self.statusmsg: str = ''
        self.statusmsg_time: int = 0
        self.dirty: int = 0
        self.quit_times: int = APEIRON_QUIT_TIMES
        self.mode_editor: int = 0
        self.dir: List[str] = list()
        self.focus_on: str = ""
        self.start_time = time.time()

    def change_mode(self):
        self.mode_editor = (self.mode_editor + 1) % 3
        self.dir = sorted(os.listdir(PATH_AGENDA))
        if self.mode_editor == 1:
            # os.system("wmctrl -r '~/dev/perso/apeiron' -b toggle,above")
            os.system(
                "wmctrl -r '~/dev/perso/apeiron' -e 0,50,50,786,527")
            self.set_status_message("Mode RÉPERTOIRE")

        if self.mode_editor == 2:
            os.system(
                "wmctrl -r ' ~/dev/perso/apeiron' -e 0,50,50,800,50")
            os.system("wmctrl -r ' ~/dev/perso/apeiron' -b add,above")
            self.set_status_message("Mode FOCUS")
            if len(self.row) == 0:
                self.focus_on = "Aucune tâche en cours."
            else:
                self.focus_on = self.row[self.cy].render
        else:
            os.system(
                "wmctrl -r ' ~/dev/perso/apeiron' -b remove,above")
            os.system(
                "wmctrl -r ' ~/dev/perso/apeiron' -e 0,50,50,786,527")
            self.set_status_message(DEFAULT_STATUS_MSG)

    def set_status_message(self, msg):
        self.statusmsg = msg
        self.statusmsg_time = time.time()

    def scroll(self):
        if self.cy < self.rowoff:
            self.rowoff = self.cy
        if self.cy >= self.rowoff + self.screenrows:
            self.rowoff = self.cy - self.screenrows + 1
        if self.cx < self.coloff:
            self.coloff = self.cx
        if self.cx >= self.coloff + self.screencols:
            self.coloff = self.cx - self.screencols + 1

    def prompt(self, prompt: str):
        buf = ""
        buflen = 0

        while True:
            self.set_status_message(prompt + buf + '\0')
            Draw.refresh_screen(e, fd)
            c = Keyboard.read_key()
            while c == '':
                c = Keyboard.read_key()
            if c == DEL_KEY or c == BACKSPACE:
                if buflen > 0:
                    buflen -= 1
                    buf = buf[:buflen]
            elif c == ESC:
                self.set_status_message("")
                return
            elif c == ENTER:
                if buflen != 0:
                    self.set_status_message("")
                    return buf[:buflen-1]
            elif c in string.printable and ord(c) < 128:
                buf += c
                buflen += 1

    def autosave(self):
        current = str(time.time())
        with open(TEMP_FOLDER + TEMP_FILENAME + "_" + current + ".txt", 'w+') as f:
            for r in self.row:
                f.write(str(r.chars[:r.size-2]))
                f.write(str('\n'))
            if self.mode_editor == 0:
                self.set_status_message("Sauvegarde temporaire effectuée.")
            f.close()

    def delete_temp_files(self):
        list_temp_dir = os.listdir(TEMP_FOLDER)
        log(list_temp_dir)
        for file in list_temp_dir:
            timed = file[len(TEMP_FILENAME)+1:-4]
            if float(timed) > self.start_time:
                os.remove(TEMP_FOLDER + file)

    def save(self):
        if self.filename == '':
            self.filename = self.prompt(
                "(ESC pour annuler) Enregistrer sous : ")
            if self.filename == "":
                self.set_status_message("Sauvegarde annulée.")
                return

        with open(PATH_AGENDA + self.filename, 'w+') as f:
            for r in self.row:
                f.write(str(r.chars[:r.size-2]))
                f.write(str('\n'))
        self.set_status_message("Sauvegarde effectuée.")
        f.close()
        self.dirty = 0
        self.delete_temp_files()

    def find(self):
        query = self.prompt("(ESC pour annuler) Recherche: ")
        if query == "":
            return
        for i in range(self.numrows):
            match = query in self.row[i].render
            if match:
                self.cy = i
                self.cx = self.row[i].render.find(query)
                self.rowoff = self.numrows
                break

    def open(self, filename: str):
        self.filename = filename
        self.numrows = 0
        if os.path.exists(filename):
            with open(PATH_AGENDA + filename, 'r') as file1:
                row = file1.readline()
                while (len(row) > 0 and row != "EOF"):
                    log("does this works?")
                    self.insert_row(row[:len(row)-1], self.numrows)
                    row = file1.readline()

            file1.close()
        self.dirty = 0

    def update_row(self, at: int):
        self.row[at].render = ""
        self.row[at].render = self.row[at].chars + '\0'
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


class Keyboard():
    @staticmethod
    def ctrl(key):
        return chr(ord(key) & 0x1f)

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

    @staticmethod
    def move_cursor(key, e: Editor):
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


class Draw():
    @staticmethod
    def rows(abuffer, e):
        if e.mode_editor == 0:
            Draw.mode_editor(abuffer, e)
        elif e.mode_editor == 1:
            Draw.mode_dir(abuffer, e)
        elif e.mode_editor == 2:
            Draw.mode_focus(abuffer, e)

    @staticmethod
    def mode_focus(abuffer, e):
        abuffer.append(e.focus_on, len(e.focus_on)-1)
        abuffer.append("\x1b[K", 3)
        abuffer.append("\r\n", 2)
        log(abuffer)

    @staticmethod
    def mode_dir(abuffer, e):
        nb_elem = 0
        for f in e.dir:
            abuffer.append(f, len(f))
            abuffer.append("\x1b[K", 3)
            abuffer.append("\r\n", 2)
            nb_elem += 1
            if nb_elem == e.screenrows:
                break

    @staticmethod
    def mode_editor(abuffer, e):
        for y in range(e.screenrows):
            filerow = y + e.rowoff
            if filerow >= e.numrows:
                if e.numrows == 0 and y == e.screenrows/3:
                    welcome = "Bienvenue sur Apeiron, version " + APEIRON_VERSION
                    welcomelen = sys.getsizeof(welcome)
                    if welcomelen > e.screencols:
                        welcomelen = e.screencols
                    abuffer.append(welcome, welcomelen)
                else:
                    abuffer.append("~", 1)
            else:
                ln = e.row[filerow].rsize - e.coloff
                if ln < 0:
                    ln = 0
                if ln > e.screencols:
                    ln = e.screencols
                abuffer.append(e.row[filerow].render, ln)
            abuffer.append("\x1b[K", 3)
            abuffer.append('\r\n', 2)

    @staticmethod
    def status_bar(abuffer, e):
        abuffer.append("\x1b[7m", 4)
        status = e.filename
        if e.dirty > 0:
            status = status + " (modified)"

        if e.mode_editor == 2:
            status = " APEIRON : appuyez sur Ctrl-D pour revenir en mode éditeur."

        ln = len(status)
        if ln > e.screencols:
            ln = e.screencols
        abuffer.append(status, ln)
        while ln < e.screencols:
            abuffer.append(" ", 1)
            ln = ln + 1
        abuffer.append("\x1b[m", 3)
        abuffer.append("\r\n", 2)

    @staticmethod
    def message_bar(abuffer, e):
        abuffer.append("\x1b[K", 3)
        msgln = len(e.statusmsg)
        if msgln > e.screencols:
            msgln = e.screencols
        if msgln and time.time() - e.statusmsg_time < 5:
            abuffer.append(e.statusmsg, msgln)

    @staticmethod
    def refresh_screen(e, fd):
        abuffer = Buffer()
        e.scroll()
        abuffer.append('\x1b[?25l', 6)
        abuffer.append('\x1b[H', 3)

        Draw.rows(abuffer, e)
        if e.mode_editor == 2:
            abuffer.append("\x1b[K", 3)
            abuffer.append("\r\n", 2)
        if e.mode_editor == 0 or e.mode_editor == 2:
            Draw.status_bar(abuffer, e)
        Draw.message_bar(abuffer, e)
        # if e.mode_editor == 2:
        #     abuffer.append("\x1b[K", 3)
        #     abuffer.append("\r\n", 2)

        if e.mode_editor == 0:
            buf = "\x1b[" + str(e.cy + 1 - e.rowoff) + ";" + \
                str(e.cx + 1 - e.coloff) + "H"
        elif e.mode_editor == 1:
            buf = "\x1b[" + str(e.dir_cy + 1 - e.rowoff) + ";" + \
                str(e.cx + 1 - e.coloff) + "H"
        if e.mode_editor != 2:
            bufsize = sys.getsizeof(buf)
            abuffer.append(buf, bufsize)

        abuffer.append('\x1b[?25h', 6)
        temp = ''.join(str(abuffer.b))
        temp2 = ""
        for elem in (abuffer.b):
            temp2 = temp2 + elem
        os.write(fd, bytes(temp2, encoding="utf-8"))
        abuffer.free()


if __name__ == "__main__":
    try:
        logfile = open("log.txt", 'a')
        log("This is a new session!")
        fd, atexit = Config.enableRawMode()
        hw = Config.getWindowSize()
        e = Editor(fd, atexit, hw[0], hw[1])
        if len(sys.argv) >= 2:
            print(sys.argv[1])
            e.filename = sys.argv[1]
            e.open(sys.argv[1])

        e.set_status_message(
            DEFAULT_STATUS_MSG)

        while True:
            Draw.refresh_screen(e, fd)
            Keyboard.process_keypress(e)
            e.autosave()
    except:
        Config.disableRawMode(e)
        raise
