"""Intentional GTK help: concise tooltips and lazy, keyboard-accessible explanation popovers."""
import gi
gi.require_version('Gtk','3.0')
from gi.repository import Gtk, Gdk, Pango
from pathlib import Path
from .help_content import TOPICS, tooltip_text


def install_help_styles(screen):
    provider=Gtk.CssProvider()
    provider.load_from_path(str(Path(__file__).with_name('context_help.css')))
    Gtk.StyleContext.add_provider_for_screen(screen,provider,Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION+1)
    return provider


def contextual(widget,key):
    """Declare a control's intentional help source, including accessible descriptive text."""
    description=tooltip_text(key)  # Unknown IDs fail immediately, not at a later hover.
    widget._gafaw_help_key=key
    widget.get_accessible().set_description(description)
    return widget


def short_help(widget,key):
    contextual(widget,key)
    widget.set_tooltip_text(tooltip_text(key))
    return widget


def no_help(widget,reason):
    """Explicit exemption for an obvious parameter control; checked by the GUI help audit."""
    if not isinstance(reason,str) or not reason.strip():raise ValueError('Explain why this control needs no help.')
    widget._gafaw_help_exempt_reason=reason
    return widget


def help_button(key):
    topic=TOPICS[key]
    trigger=Gtk.Button(label='?')
    trigger.set_relief(Gtk.ReliefStyle.NONE);trigger.set_valign(Gtk.Align.CENTER);trigger.set_can_focus(True)
    trigger.get_style_context().add_class('gafaw-help-trigger')
    short_help(trigger,key)
    trigger.get_accessible().set_name('Help: '+topic.title)
    trigger.get_accessible().set_description('Open a contextual explanation with Enter or Space; Escape closes it.')
    trigger._gafaw_help_popover=None

    def show(_):
        popover=trigger._gafaw_help_popover
        if popover is None:
            popover=Gtk.Popover.new(trigger);trigger._gafaw_help_popover=popover
            popover.get_style_context().add_class('gafaw-help')
            popover.set_position(Gtk.PositionType.BOTTOM)
            popover.get_accessible().set_name(topic.title)
            content=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=12);content.set_border_width(16)
            heading=Gtk.Label(label=topic.title,xalign=0);heading.set_line_wrap(True)
            heading.get_style_context().add_class('help-heading');content.pack_start(heading,False,False,0)
            paragraphs=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=10)
            for text in topic.paragraphs:
                body=Gtk.Label(label=text,xalign=0)
                body.set_line_wrap(True);body.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
                body.set_width_chars(44);body.set_max_width_chars(48);body.set_selectable(True)
                paragraphs.pack_start(body,False,False,0)
            reading=Gtk.ScrolledWindow();reading.set_policy(Gtk.PolicyType.NEVER,Gtk.PolicyType.AUTOMATIC)
            reading.set_propagate_natural_height(True);reading.set_max_content_height(340)
            reading.set_propagate_natural_width(True);reading.add(paragraphs)
            content.pack_start(reading,True,True,0)
            hub=getattr(trigger.get_toplevel(),'_gafaw_help_controller',None)
            if hub:
                links=Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL,spacing=8)
                more=Gtk.Button(label='Learn More');more.connect('clicked',lambda *_:(popover.popdown(),hub.open_guide(key)))
                stanley=Gtk.Button(label='Ask Stanley');stanley.connect('clicked',lambda *_:(popover.popdown(),hub.ask(key)))
                links.pack_start(more,False,False,0);links.pack_start(stanley,False,False,0)
                popover._gafaw_stanley_link=stanley
                stanley.set_no_show_all(not hub.prefs.data['stanley']);stanley.set_visible(hub.prefs.data['stanley'])
                content.pack_start(links,False,False,0)
            close=Gtk.Button(label='Close');close.set_halign(Gtk.Align.END)
            close.connect('clicked',lambda *_:popover.popdown());content.pack_start(close,False,False,0)
            popover.add(content)
            popover._gafaw_close=close
            def escape(_,event):
                if event.keyval==Gdk.KEY_Escape:popover.popdown();return True
                return False
            popover.connect('key-press-event',escape)
            popover.connect('closed',lambda *_:trigger.grab_focus() if trigger.get_mapped() else None)
            trigger.connect('destroy',lambda *_:popover.destroy())
        if popover.get_visible():popover.popdown()
        else:
            popover.show_all();popover.popup();popover._gafaw_close.grab_focus()
    trigger.connect('clicked',show)
    def activate_key(_,event):
        if event.keyval in (Gdk.KEY_Return,Gdk.KEY_KP_Enter,Gdk.KEY_space):
            trigger.clicked();return True
        return False
    trigger.connect('key-press-event',activate_key)
    return trigger


def help_label(text,key,style=None,control=None,wrap=False):
    row=Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL,spacing=6)
    caption=Gtk.Label(label=text,xalign=0)
    if style:caption.get_style_context().add_class(style)
    if wrap:caption.set_line_wrap(True);caption.set_max_width_chars(80)
    if control is not None:
        contextual(control,key);caption.set_mnemonic_widget(control)
    row.pack_start(caption,False,True,0);row.pack_start(help_button(key),False,False,0)
    return row


def with_help(widget,key):
    contextual(widget,key)
    row=Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL,spacing=6)
    row.pack_start(widget,True,True,0);row.pack_start(help_button(key),False,False,0)
    return row


def missing_parameter_help(root):
    """Focused audit: reject unexplained technical selectors/ranges; never invent generic help."""
    missing=[]
    def visit(widget):
        if isinstance(widget,(Gtk.SpinButton,Gtk.ComboBox,Gtk.Range)):
            if not getattr(widget,'_gafaw_help_key',None) and not getattr(widget,'_gafaw_help_exempt_reason',None):missing.append(widget)
        if isinstance(widget,Gtk.Container):
            for child in widget.get_children():visit(child)
    visit(root)
    return missing
