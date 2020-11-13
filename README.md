# apeiron

a simple text editor in python, based on this tutorial : [https://viewsourcecode.org/snaptoken/kilo/](https://viewsourcecode.org/snaptoken/kilo/)

**Nov 2020 note**: this project is a personal project that is currently **shelved**. do not expect any changes soon.

## in short

In July 2020, I was using a text editor that had too many features for what I was doing - and it was keeping me from being able to focus.

I had the idea to write a text editor that would do just that - and shortly went on finding ways to do this. The apeiron project is the result of this idea.

## in long

After having that idea and starting my search, I discovered the snaptoken tutorial where the antirez' kilo text editor is implemented. Given the extensive comments made in the tutorial, I thought it would be a good learning opportunity and soon started that project, with the hope to finish it and include it in my data-analyst-to-dev portfolio. 

I decided to programm in Python instead of C, because I wanted to keep myself from doing too much copy-pasting code along the tutorial, instead of really taking the time to understand what that code was doing.

I was halfway through doing that project when I started the Recurse Center in late September 2020. I decided to keep working on this project - and so did, for the best part of the first half of my batch. I gave at least 3 talks on things I learned about computers while writing a text editor: the history of the control characters! the difference between canonical and raw mode! how a screen refreshes! That last one paved the way to one of my current project (writing an OS for a Raspberry Pi), also based on a [tutorial](https://www.cl.cam.ac.uk/projects/raspberrypi/tutorials/os/).

## improving the code

After writing the first version of apeiron, with absolutely no classes as a way to keep the code as close as possible to the tutorial, I decided to do a first refactor (this is the code in the `try_it_here` folder, in the `main.py`) to make the code clearer for the programmer - and easier to update. 

That went well, and I wanted to improve the code again - and to get rid of the too-many bugs - and to make it easy to add a small set of features. 

So I am now in the `wip` (work in progress) folder, working on improving the boundaries of my classes.

## ... and now ? you said you were shelving this ?

Yes - I would love to finish this project and start using it, but I also want to finish the [montréal public library project](https://github.com/eviau/catalogue_biblio) and there is only so much time left to my RC batch! 

I know I will make good mileage on the apeiron in the future though, so I wanted to take the time to properly archives this for now, as to make it easy to pick it up again in the future.
