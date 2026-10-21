"""GTK parameter widgets keep wheel events for the containing page, never values."""
import gi
gi.require_version('Gtk','3.0')
from gi.repository import Gtk, Gdk


def protect_parameters(widget):
    """Protect existing and subsequently added controls, including editable combos."""
    if getattr(widget,'_gafaw_wheel_protected',False):return
    widget._gafaw_wheel_protected=True
    if isinstance(widget,(Gtk.SpinButton,Gtk.ComboBox,Gtk.Range)):
        widget.add_events(Gdk.EventMask.SCROLL_MASK | Gdk.EventMask.SMOOTH_SCROLL_MASK)
        widget.connect('scroll-event',_page_scroll)
    if isinstance(widget,Gtk.Container):
        for child in widget.get_children():protect_parameters(child)
        widget.connect('add',lambda _,child:protect_parameters(child))


def _page_scroll(widget,event):
    parent=widget.get_parent()
    while parent is not None:
        if isinstance(parent,Gtk.ScrolledWindow):
            parent.event(event)
            break
        parent=parent.get_parent()
    # Handled even without a page: never invoke a parameter's default wheel action.
    return True
