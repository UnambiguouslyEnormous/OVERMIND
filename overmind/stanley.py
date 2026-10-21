"""Original MIT-licensed vector stapler. Native GTK image decoding; no Cairo bridge needed.

The SVG scene is generated from bounded internal state, never imported markup.
Idle samples at 2 Hz; brief gestures at 12.5 Hz. Hidden/static actors have no
animation source. GTK's vector icon loader handles HiDPI without a GPU framework.
"""
import math
import time
import gi
gi.require_version('Gtk','3.0')
from gi.repository import Gtk, GLib, Gio, Atk, Gdk

STATES={'idle','speaking','greeting','confused','sideeye','celebrate','concerned','sleepy'}


def stanley_svg(state='idle',phase=0,motion=True):
    """Deterministic, original artwork source shared by the runtime and regeneration tool."""
    if state not in STATES:raise ValueError('Unknown Stanley gesture')
    t=phase if motion else 0
    bounce=-abs(math.sin(t*6))*9 if state in ('greeting','celebrate') else math.sin(t*2)*1.1 if motion else 0
    angle=-7
    if state=='speaking':angle-=7*(1+math.sin(t*18))
    if state=='confused':angle-=8
    if state=='concerned':angle-=2
    if state=='celebrate':angle=-1-14*abs(math.sin(t*9))
    blink=state=='sleepy' or (motion and 0<t%4.6<.15)
    shift=4 if state=='sideeye' else math.sin(t*.7)*2 if motion else 0
    eyes=[]
    for x in (117,149):
        if blink:eyes.append(f'<path d="M{x-10} 62l20 1" stroke="#badfc7" stroke-width="3"/>')
        else:eyes.append(f'<rect x="{x-12}" y="52" width="23" height="20" rx="8" fill="#e8f5e3"/><circle cx="{x+shift:.2f}" cy="63" r="5" fill="#122b29"/><circle cx="{x+shift-1:.2f}" cy="61" r="1.4" fill="#edfff5"/>')
        eyebrow=(5 if x==117 else -3) if state in ('confused','concerned','sideeye') else 0
        eyes.append(f'<path d="M{x-10} {47+eyebrow}L{x+9} 47" stroke="#a8c2bd" stroke-width="3"/>')
    ribs=''.join(f'<path d="M69 {y}h94"/>' for y in range(77,95,4))
    top_ribs=''.join(f'<path d="M{x} 61l18 1"/>' for x in range(55,94,6))
    marks='<path d="M183 29h8m-4-4v8M25 35h8m-4-4v8M203 69h8m-4-4v8" stroke="#c4f2a6" stroke-width="2"/>' if state=='celebrate' else ''
    # Sleep mark is a path, so the mascot has no font dependency.
    if state=='sleepy':marks='<path d="M184 25h9l-9 10h9" fill="none" stroke="#a8d1c2" stroke-width="2"/>'
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="220" height="150" viewBox="0 0 220 150">
<defs><linearGradient id="base" x1="0" y1="0" x2="0" y2="1"><stop stop-color="#a6b8ba"/><stop offset="0.25" stop-color="#526469"/><stop offset="1" stop-color="#1f2b33"/></linearGradient><linearGradient id="shell" x1="0" y1="0" x2="0" y2="1"><stop stop-color="#8ca1a6"/><stop offset="0.15" stop-color="#45575e"/><stop offset="1" stop-color="#142129"/></linearGradient></defs>
<g transform="translate(0,{bounce:.2f})"><ellipse cx="110" cy="132" rx="85" ry="8" fill="#000000" opacity="0.28"/>
<rect x="24" y="113" width="175" height="17" rx="7" fill="#121a1f"/><rect x="23" y="99" width="178" height="25" rx="8" fill="url(#base)" stroke="#b8ccc9" stroke-width="1.5"/>
<path d="M102 100l93 1 7 9-95-1z" fill="#d6e3d4"/><rect x="151" y="103" width="23" height="4" rx="2" fill="#21332e"/>
<rect x="32" y="69" width="145" height="31" rx="5" fill="#3b4a4f"/><g stroke="#5e7070" stroke-width="1">{ribs}</g>
<circle cx="47" cy="87" r="20" fill="#141f21"/><circle cx="47" cy="87" r="9" fill="#9cb0b0"/><circle cx="47" cy="87" r="4" fill="#243638"/>
<g transform="rotate({angle:.2f},44,80)"><path d="M42 50C65 30 158 32 186 53L189 77C144 81 90 77 42 74Z" fill="url(#shell)" stroke="#adc4c4" stroke-width="2"/>
<path d="M56 51C94 39 145 42 170 54L167 58C128 49 90 49 57 56Z" fill="#5cc287"/><g stroke="#4f636b" stroke-width="0.7">{top_ribs}</g>
<rect x="175" y="63" width="13" height="15" rx="2" fill="#b5c7c9"/>{''.join(eyes)}</g>
<circle cx="44" cy="115" r="3" fill="#6eee9c"/>{marks}</g></svg>'''


class StanleyActor(Gtk.Image):
    def __init__(self,width=110,height=75):
        super().__init__();self.set_size_request(width,height);self.set_pixel_size(width)
        self.state='idle';self.until=0;self.last_activity=time.monotonic();self.source=None;self.reduced=False;self.obscured=False;self.window=None;self.window_handler=None
        self.get_accessible().set_role(Atk.Role.IMAGE);self.get_accessible().set_name('Stanley the Stapler')
        self.get_accessible().set_description('Original animated laboratory assistant; gestures are moods, never scientific metrics.')
        self.connect('map',self.mapped);self.connect('unmap',lambda *_:self.stop())
        self.connect('destroy',self.destroy_actor)
        self.settings=Gtk.Settings.get_default();self.settings_handler=self.settings.connect('notify::gtk-enable-animations',lambda *_:self.motion(self.reduced))
        self.frame()

    def mapped(self,*_):
        top=self.get_toplevel()
        if isinstance(top,Gtk.Window) and top is not self.window:
            self.disconnect_window();self.window=top
            self.window_handler=top.connect('window-state-event',self.window_state)
        native=top.get_window()
        if native:self.obscured=bool(native.get_state()&(Gdk.WindowState.ICONIFIED|Gdk.WindowState.WITHDRAWN))
        self.frame();self.schedule()

    def disconnect_window(self):
        if self.window and self.window_handler and self.window.handler_is_connected(self.window_handler):self.window.disconnect(self.window_handler)
        self.window=None;self.window_handler=None

    def window_state(self,_,event):
        self.obscured=bool(event.new_window_state&(Gdk.WindowState.ICONIFIED|Gdk.WindowState.WITHDRAWN))
        if self.obscured:self.stop()
        else:self.schedule()
        return False

    def static(self):return self.reduced or not self.settings.get_property('gtk-enable-animations')

    def destroy_actor(self,*_):
        self.stop();self.disconnect_window()
        if self.settings_handler:self.settings.disconnect(self.settings_handler);self.settings_handler=None

    def stop(self):
        if self.source:GLib.source_remove(self.source);self.source=None

    def motion(self,reduced):
        self.reduced=reduced;self.stop();self.frame();self.schedule()

    def play(self,state,duration=2.4):
        if state not in STATES:raise ValueError('Unknown Stanley gesture')
        self.state=state;self.until=time.monotonic()+duration;self.last_activity=time.monotonic()
        self.get_accessible().set_description('Stanley’s expression: '+state+'. Consult the text for factual help.')
        self.stop();self.frame();self.schedule()

    def schedule(self):
        if self.source or self.obscured or not self.get_mapped() or self.static():return
        self.source=GLib.timeout_add(500 if self.state in ('idle','sleepy') else 80,self.tick)

    def tick(self):
        self.source=None
        now=time.monotonic()
        if self.state not in ('idle','sleepy') and now>=self.until:self.state='idle'
        if self.state=='idle' and now-self.last_activity>180:self.state='sleepy'
        self.frame();self.schedule();return False

    def frame(self):
        svg=stanley_svg(self.state,time.monotonic(),not self.static()).encode()
        self.set_from_gicon(Gio.BytesIcon.new(GLib.Bytes.new(svg)),Gtk.IconSize.DIALOG)
