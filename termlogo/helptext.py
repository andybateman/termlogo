"""Help table: one line per primitive, `name | usage | description`, grouped by category."""

import textwrap

from .registry import PRIMS

TABLE = """
== Control
repeat | repeat n [instructions] | Run the instructions n times. REPCOUNT gives the current count.
forever | forever [instructions] | Run the instructions until an error, STOP or Ctrl-C.
repcount | repcount | The number of the current REPEAT/FOREVER/FOREACH pass, starting at 1.
if | if test [then] | Run the list if test is true. (if test [then] [else]) also works in parentheses.
ifelse | ifelse test [then] [else] | Run one list or the other. Outputs the list's value if it has one.
test | test condition | Remember a condition for IFTRUE and IFFALSE.
iftrue | iftrue [instructions] | Run the list if the last TEST was true. Alias: IFT.
iffalse | iffalse [instructions] | Run the list if the last TEST was false. Alias: IFF.
while | while [condition] [instructions] | Repeat while the condition list outputs true.
until | until [condition] [instructions] | Repeat until the condition list outputs true.
do.while | do.while [instructions] [condition] | Run once, then repeat while the condition is true.
do.until | do.until [instructions] [condition] | Run once, then repeat until the condition is true.
for | for [var start limit step] [instructions] | Count var from start to limit. Step is optional.
stop | stop | Leave the current procedure.
output | output value | Leave the current procedure, returning value. Alias: OP.
bye | bye | Leave Logo.
run | run [instructions] | Run a list as code. Outputs the last value if it makes one.
runresult | runresult [instructions] | Like RUN, but outputs a list holding the value, or [] if none.
wait | wait n | Pause for n sixtieths of a second (and redraw the canvas).
catch | catch "tag [instructions] | Run the list; THROW "tag jumps back here. CATCH "ERROR traps errors.
throw | throw "tag | Jump to the matching CATCH. (throw "tag value) passes a value.
error | error | After CATCH "ERROR caught something, outputs [code message procedure line].

== Variables and procedures
make | make "name value | Set a variable. Names are case-insensitive and scope is dynamic.
name | name value "name | Like MAKE with the inputs the other way round.
thing | thing "name | The value of a variable. :name is shorthand.
local | local "name | Make a variable local to the current procedure. (local "a "b) takes several.
localmake | localmake "name value | Make and set a local variable.
global | global "name | Declare a global variable.
namep | namep "name | True if the variable exists. Alias: NAME?
procedurep | procedurep "name | True if a procedure of that name is defined. Aliases: PROCEDURE?, DEFINEDP.
primitivep | primitivep "name | True if the name is a built-in command. Alias: PRIMITIVE?
erase | erase "name | Delete a procedure. Alias: ER.
erall | erall | Delete every procedure and variable.
define | define "name [[inputs] [line] ...] | Build a procedure from a list.
text | text "name | A procedure's definition as a list, suitable for DEFINE.
pots | pots | Print the title line of every procedure.
pons | pons | Print every global variable as a MAKE line.
po | po "name | Print a procedure's full definition.
load | load "file | Run a Logo source file, adding its procedures.
save | save "file | Write all procedures and variables to a file that LOAD can read back.

== Templates
foreach | foreach list template | Run the template once per item, with ? as the item.
map | map template list | A list of the template's value for each item. Eg: map [? * 2] [1 2 3]
filter | filter template list | The items for which the template is true.
find | find template list | The first item for which the template is true, else [].
reduce | reduce template list | Combine items with a two-input template (?1, ?2). Eg: reduce [?1 + ?2] [1 2 3]
apply | apply template [inputs] | Call a template or procedure name with a list of inputs.
invoke | invoke template input... | Call a template with the inputs given (use parentheses for several).

== Input and output
print | print thing | Print a word or list without its outer brackets. Alias: PR.
type | type thing | Print without a newline.
show | show thing | Print a list with its brackets.
readword | readword | Read a line of typed input as one word. Alias: RW.
readlist | readlist | Read a line of typed input as a list. Alias: RL.
cleartext | cleartext | Clear the text area. Alias: CT.

== Words and lists
word | word a b | Join words. (word a b c) takes more.
list | list a b | Make a list of the inputs. (list a b c) takes more.
sentence | sentence a b | Join inputs into one flat list. Alias: SE.
fput | fput item list | Put an item at the front of a list.
lput | lput item list | Put an item at the end of a list.
combine | combine a b | FPUT if b is a list, otherwise WORD.
reverse | reverse list | Reverse a list or word.
remove | remove item list | The list without any copies of item.
remdup | remdup list | The list with duplicates removed.
iseq | iseq from to | The integers from..to as a list. Counts down if from > to.
rseq | rseq from to count | count evenly spaced numbers from..to.
first | first thing | First item of a list, or first letter of a word.
last | last thing | Last item or letter.
butfirst | butfirst thing | All but the first item or letter. Alias: BF.
butlast | butlast thing | All but the last item or letter. Alias: BL.
item | item n thing | The nth item or letter (counting from 1).
pick | pick list | A random item.
count | count thing | How many items or letters.
member | member item list | The list from the first match onwards, else [].
memberp | memberp item list | True if the item is in the list. Alias: MEMBER?
emptyp | emptyp thing | True for [] or the empty word. Alias: EMPTY?
listp | listp thing | True if a list. Alias: LIST?
wordp | wordp thing | True if a word. Alias: WORD?
numberp | numberp thing | True if a number. Alias: NUMBER?
equalp | equalp a b | True if equal (words ignore case). Same as a = b. Alias: EQUAL?
notequalp | notequalp a b | True if not equal. Same as a <> b. Alias: NOTEQUAL?
beforep | beforep a b | True if word a sorts before b. Alias: BEFORE?
uppercase | uppercase word | Convert to upper case.
lowercase | lowercase word | Convert to lower case.
char | char n | The character with that code.
ascii | ascii char | The code of a character.

== Logic
and | and a b | True if all inputs are true. Inputs may be [lists] to run. (and a b c) takes more.
or | or a b | True if any input is true.
not | not a | Reverse true and false.

== Arithmetic
sum | sum a b | Add. (sum a b c) takes more. Same as a + b.
difference | difference a b | a - b.
product | product a b | Multiply. (product a b c) takes more. Same as a * b.
quotient | quotient a b | a / b. With one input, 1 / a.
remainder | remainder a b | Remainder with the sign of a.
modulo | modulo a b | Remainder with the sign of b.
intquotient | intquotient a b | Whole-number division.
minus | minus a | Negate.
abs | abs a | Absolute value.
int | int a | Drop the fraction.
round | round a | Nearest whole number.
sqrt | sqrt a | Square root.
power | power a b | a to the power b. Same as a ^ b.
exp | exp a | e to the power a.
ln | ln a | Natural logarithm.
log10 | log10 a | Base-10 logarithm.
pi | pi | 3.14159...
sin | sin degrees | Sine of an angle in degrees.
cos | cos degrees | Cosine of an angle in degrees.
tan | tan degrees | Tangent of an angle in degrees.
arctan | arctan x | Arc tangent in degrees. (arctan x y) gives the angle of the point.
arcsin | arcsin x | Arc sine in degrees.
arccos | arccos x | Arc cosine in degrees.
random | random n | A random whole number from 0 to n-1 in UCBLogo mode, or 1 to n in Terrapin mode. (random a b) gives a..b in either mode.
rerandom | rerandom | Reseed the random numbers. (rerandom seed) makes runs repeatable.
lessp | lessp a b | a < b. Alias: LESS?
greaterp | greaterp a b | a > b. Alias: GREATER?
lessequalp | lessequalp a b | a <= b. Alias: LESSEQUAL?
greaterequalp | greaterequalp a b | a >= b. Alias: GREATEREQUAL?
bitand | bitand a b | Bitwise and.
bitor | bitor a b | Bitwise or.
bitxor | bitxor a b | Bitwise exclusive or.
ashift | ashift a n | Shift left by n bits (right if n is negative).

== Turtle movement
forward | forward n | Move n steps in the direction the turtle faces. Alias: FD.
back | back n | Move n steps backwards. Aliases: BK, BACKWARD.
left | left degrees | Turn anticlockwise. Alias: LT.
right | right degrees | Turn clockwise. Alias: RT.
home | home | Go to [0 0] facing up.
setpos | setpos [x y] | Move to a position.
setxy | setxy x y | Move to a position.
setx | setx x | Move horizontally to x.
sety | sety y | Move vertically to y.
setheading | setheading degrees | Face a compass heading (0 is up, 90 is right). Alias: SETH.
arc | arc degrees radius | Draw an arc centred on the turtle, clockwise from its heading.
dot | dot [x y] | Plot one dot at a position.

== Turtle queries
pos | pos | The position as [x y].
xcor | xcor | The x coordinate.
ycor | ycor | The y coordinate.
heading | heading | The heading in degrees.
towards | towards [x y] | The heading that would face that position.
distance | distance [x y] | The distance to a position.
scrunch | scrunch | The aspect ratio, always [1 1] here.
shownp | shownp | True if the turtle is visible. Alias: SHOWN?
pendownp | pendownp | True if the pen is down. Alias: PENDOWN?
penmode | penmode | PAINT, ERASE or REVERSE.
pen | pen | The pen state: penup, pendown, penerase or penreverse.
pencolor | pencolor | The current pen colour: the original input in UCBLogo mode, or [red green blue alpha] in Terrapin mode. NZ spelling: PENCOLOUR.
background | background | The background colour: the original input in UCBLogo mode, or [red green blue alpha] in Terrapin mode. NZ spelling: BACKGROUNDCOLOUR.
colors | colours | Available colour names. Terrapin mode uses indexed Web colours; UCBLogo mode uses its existing palette. US spelling: COLORS.
pensize | pensize | The pen size as [n n].
wrapp | wrapp | True in WRAP mode. Alias: WRAP?

== Pen and colour
penup | penup | Lift the pen. Alias: PU.
pendown | pendown | Lower the pen. Alias: PD.
penpaint | penpaint | Draw normally with the pen down. Alias: PPT.
penerase | penerase | Pen down, erasing what it crosses. Alias: PE.
penreverse | penreverse | Pen down, toggling dots on and off. Alias: PX.
setpencolor | setpencolour colour | Set the pen colour. UCBLogo: 0-15, names or RGB 0-100. With --colour-mode terrapin: Web names, 0-138 or RGB 0-255 with optional alpha 0-1. US spelling: SETPENCOLOR.
setbackground | setbackground colour | Set the background without changing existing strokes. Uses the selected colour rules; NZ/US spellings are accepted.
setpen | setpen [penstate colour] | Set pen state and colour together. Use full state names: PENUP, PENDOWN, PENERASE or PENREVERSE.
setalpha | setalpha n | Set the default alpha (0-1) for subsequent pen colours in Terrapin mode. Explicit RGBA inputs override it; background colours use alpha 1 unless supplied.
alpha | alpha | The default alpha for subsequent pen colours (initially 1).
setpensize | setpensize n | Pen width in pixels. Alias: SETWIDTH.
setpalette | setpalette n [r g b] | Redefine a UCBLogo palette colour (RGB 0-100; UCBLogo mode only).
palette | palette n | A UCBLogo palette colour as [r g b] (UCBLogo mode only).

== Screen
hideturtle | hideturtle | Hide the turtle marker. Alias: HT.
showturtle | showturtle | Show the turtle marker. Alias: ST.
clearscreen | clearscreen | Clear the drawing and send the turtle home. Alias: CS.
clean | clean | Clear the drawing but leave the turtle where it is.
wrap | wrap | Turtle wraps round the edges of the canvas.
window | window | Turtle may wander off-screen (the default).
fence | fence | Turtle may not leave the canvas: moving out is an error.
fill | fill | Flood-fill with the pen colour. In Terrapin mode, the pen must be PENDOWN; (FILL tolerance) accepts 0-1, default 0.5, to cross transparent borders. An area enclosed by pen lines becomes a cut-out in a STENCIL.
filled | filled colour [instructions] | Run the instructions, then fill the polygon through every point the turtle visited (pen up or down), back to where it started, and outline it in the pen colour. Where the path crosses itself, alternate regions are filled. The shape becomes a cut-out in a STENCIL.
label | label thing | Write text at the turtle's position.
setspeed | setspeed n | Watch it draw: 0 is instant, 1 is slow, 5 is the default, 10 is fast. Each step doubles the speed.
speed | speed | The current SETSPEED value.
setscale | setscale n | Pixels per turtle step (default 1). Extension. 0.5 halves drawings.
textscreen | textscreen | Accepted and ignored. Also FULLSCREEN, SPLITSCREEN (TS, FS, SS).
savepict | savepict "file.svg | Export the drawing as .svg, .png, .txt or .stl (a stencil). Alias: SAVEPIC.
stencil | stencil "file  or  (stencil "file [options]) | Export a 3D-printable stencil: a flat plate with your pen strokes cut through it as slots and your filled areas (FILL, FILLED) cut out, as a binary STL. The .stl extension is added if the name lacks it. One step is 1 mm and pen size is the slot width (SETPENSIZE 2 for 2 mm). Islands such as the centre of an O are tied back with bridges. A FILL that is not enclosed by pen lines is left out with a warning. Options: thickness 1.2, margin 8, bridge 1.6, bridges 2, width (force every slot), minwidth 0.8, plate [w h], mirror true, pitch 0.2, mm 1, maxgap 15.

== Help
help | help  or  help name  or  help "category | List all commands, or explain one command or a category (turtle, control, arithmetic...).
version | version | Output the version and author of termlogo.

== Language
to | to name :input ... (lines) end | Define a procedure. Optional inputs: [:x default]. Rest input: [:rest].
operators | + - * / ^ = <> < > <= >= | Infix operators. Parenthesised reporters work in expressions, for example (repcount + 1) and right (-1) ^ (repcount + 1). Write 3 - 4, not 3 -4 (a minus after a space is a sign).
words | "word  :variable  [list]  |a b| | Quote a word with ". |a b| holds spaces. ; starts a comment.
templates | ? ?1 ?2 [[a b] body] | Slots and lambdas used by MAP, FILTER, FOREACH and REDUCE.
colours | --colour-mode ucblogo or terrapin | UCBLogo uses palette 0-15 and RGB 0-100. Terrapin uses indexed Web colours, RGB 0-255 and optional alpha 0-1; PENCOLOR and BACKGROUND report RGBA lists. COLOURS lists names. Both grey and gray spellings are accepted.
keys | Tab, Up/Down, Alt+Enter, Escape, mouse click, Shift-drag, Ctrl-C, Ctrl-D | Tab completes names. Up recalls complete commands, including multi-line blocks and whole pasted programs; Down restores your draft. Inside a multi-line command, Up and Down move between its lines and step through history only from the first or last line; Ctrl-P and Ctrl-N (or PageUp and PageDown) always step through history. Alt+Enter adds a line break where Enter would run the command (Shift+Enter too in Ghostty and Kitty). Home and End (Ctrl-A, Ctrl-E) go to the ends of the line, and pressed again to the ends of the command; Ctrl-U and Ctrl-K delete to the start or end of the line. In a bracketed-paste terminal, paste the whole program then press Enter to run it; setup commands stay with its history entry. The command pane grows and wraps to show the source, using canvas space only when needed. Startup guidance remains until the first command starts running. Commands taller than the window scroll to keep the cursor visible. Click any visible command row to place the editing cursor, including earlier continuation lines. Escape or Ctrl-C stops drawing, waits and loops (or cancels the current command). Shift-drag selects terminal text; Cmd+C copies it on macOS. Click or left-drag on the canvas to reposition the turtle without a connector; during drawing its current movement ends there. Ctrl-D on an empty prompt, or BYE, leaves.
"""

TOPICS = {'to', 'operators', 'words', 'templates', 'colours', 'keys'}


def _parse():
    cats, entries = [], {}
    cur = None
    for line in TABLE.strip().splitlines():
        if line.startswith('== '):
            cur = line[3:].strip()
            cats.append(cur)
        elif line.strip():
            name, usage, desc = (p.strip() for p in line.split('|', 2))
            entries[name] = (cur, usage, desc)
    return cats, entries


CATEGORIES, ENTRIES = _parse()


def aliases(name):
    p = PRIMS.get(name)
    if p is None:
        return []
    return sorted(n for n, q in PRIMS.items() if q is p and n != p.name)


def canonical(name):
    p = PRIMS.get(name)
    return p.name if p else name


def overview(width=78):
    lines = [
        'Type HELP "name for one command, or HELP "category for a group. Tab completes names.',
        '',
    ]
    for cat in CATEGORIES:
        names = sorted(n for n, (c, _, _) in ENTRIES.items() if c == cat)
        lines.append(cat + ':')
        lines.extend(
            textwrap.wrap(' '.join(names), width, initial_indent='  ', subsequent_indent='  ')
        )
    return '\n'.join(lines)


def lookup(word, width=78):
    """Help text for a command name, alias or category; None if nothing matches."""
    w = word.lower().strip('"')
    if w in ('', 'all', 'commands'):
        return overview(width)
    name = canonical(w)
    if name in ENTRIES:
        cat, usage, desc = ENTRIES[name]
        out = [usage, '  ' + desc]
        al = aliases(name)
        if al and name not in TOPICS and 'Alias' not in desc:
            out.append('  Also: ' + ' '.join(al))
        return '\n'.join(
            textwrap.fill(text, width, subsequent_indent='  ') if index == 1 else text
            for index, text in enumerate(out)
        )
    for cat in CATEGORIES:
        if cat.lower() == w or cat.lower().split()[0] == w:
            names = sorted(n for n, (c, _, _) in ENTRIES.items() if c == cat)
            rows = [cat + ':'] + [f'  {ENTRIES[n][1]}\n      {ENTRIES[n][2]}' for n in names]
            return '\n'.join(rows)
    hits = sorted(n for n, (_, u, d) in ENTRIES.items() if w in d.lower() or w in n)
    if hits:
        return f'No command called {word}. Related: ' + ' '.join(hits[:12])
    return None
