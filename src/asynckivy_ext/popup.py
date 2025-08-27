__all__ = (
    'open_popup', 'Transition', 'NoTransition', 'FadeTransition', 'SlideTransition',
)

from typing import TypeAlias, Literal
from collections.abc import Callable, AsyncIterator
from contextlib import AsyncExitStack, contextmanager, asynccontextmanager, AbstractAsyncContextManager as AACM

from kivy.graphics import Translate, Rectangle, Color
from kivy.core.window import Window, WindowBase
from kivy.uix.widget import Widget
from kivy.uix.anchorlayout import AnchorLayout


import asynckivy as ak
from asynckivy import transform, StatefulEvent, anim_attrs_abbr as anim_attrs


_default_bgcolor = (0., 0., 0., .8)
Transition: TypeAlias = Callable[[Widget, 'KXPopupBackground', WindowBase], AACM[None]]
'''
Defines how a popup appears and disappears.
'''


class KXPopupBackground(AnchorLayout):
    '''
    The real parent of a popup widget.
    '''

    __events__ = ('on_touch_down_outside_popup', )

    # default value of an instance attribute
    _block_inputs = False

    def on_touch_down_outside_popup(self, touch):
        pass

    @contextmanager
    def accept_inputs(self):
        self._block_inputs = False
        try:
            yield
        finally:
            self._block_inputs = True

    def on_touch_down(self, touch):
        if self._block_inputs:
            return True
        c = self.children[0]
        if c.collide_point(*touch.opos):  # AnchorLayout is not a relative-type widget, no need for translation
            c.dispatch('on_touch_down', touch)
        else:
            self.dispatch('on_touch_down_outside_popup', touch)
        return True

    def on_touch_move(self, touch):
        if self._block_inputs:
            return True
        c = self.children[0]
        if c.collide_point(*touch.pos):
            c.dispatch('on_touch_move', touch)
        return True

    def on_touch_up(self, touch):
        if self._block_inputs:
            return True
        c = self.children[0]
        if c.collide_point(*touch.pos):
            c.dispatch('on_touch_up', touch)
        return True


class NoTransition:
    def __init__(self, *, background_color=_default_bgcolor):
        self.background_color = background_color

    @asynccontextmanager
    async def __call__(self, popup: Widget, bg: KXPopupBackground, parent: WindowBase):
        bg_canvas = bg.canvas.before
        try:
            with bg_canvas:
                Color(*self.background_color)
                rect = Rectangle()
            with ak.sync_attr((bg, 'size'), (rect, 'size')):
                yield
        finally:
            bg_canvas.clear()


class FadeTransition:
    def __init__(self, *, in_duration=.1, out_duration=.1, background_color=_default_bgcolor):
        self.in_duration = in_duration
        self.out_duration = out_duration
        self.background_color = background_color

    @asynccontextmanager
    async def __call__(self, popup: Widget, bg: KXPopupBackground, parent: WindowBase):
        bg_canvas = bg.canvas.before
        try:
            bg.opacity = 0
            with bg_canvas:
                Color(*self.background_color)
                rect = Rectangle()
            with ak.sync_attr((bg, 'size'), (rect, 'size')):
                await anim_attrs(bg, d=self.in_duration, opacity=1.0)
                yield
                await anim_attrs(bg, d=self.out_duration, opacity=0.0)
        finally:
            bg.opacity = 1.0
            bg_canvas.clear()


class SlideTransition:
    def __init__(self, *, in_duration=.2, out_duration=.2, background_color=_default_bgcolor,
                 in_curve='out_back', out_curve='in_back',
                 in_direction: Literal['left', 'right', 'down', 'up']='down'):
        self.in_duration = in_duration
        self.out_duration = out_duration
        self.background_color = background_color
        self.in_curve = in_curve
        self.out_curve = out_curve
        self.in_direction = in_direction

    @asynccontextmanager
    async def __call__(self, popup: Widget, bg: KXPopupBackground, parent: WindowBase):
        bg_canvas = bg.canvas.before
        try:
            bg_alpha = self.background_color[3]
            with bg_canvas:
                color = Color(*self.background_color[:3], 0.)
                rect = Rectangle()
            with (
                ak.sync_attr((bg, 'size'), (rect, 'size')),
                transform(popup, use_outer_canvas=True) as ig,
            ):
                x_dist = y_dist = 0
                if self.in_direction in ('up', 'down'):
                    y_dist = (bg.height + popup.height) / 2
                else:
                    x_dist = (bg.width + popup.width) / 2
                if self.in_direction in ('right', 'up'):
                    y_dist = -y_dist
                    x_dist = -x_dist
                ig.add(mat := Translate(x_dist, y_dist))
                await ak.wait_all(
                    anim_attrs(mat, d=self.in_duration, t=self.in_curve, x=0, y=0),
                    anim_attrs(color, d=self.in_duration, a=bg_alpha),
                )
                yield
                await ak.wait_all(
                    anim_attrs(mat, d=self.out_duration, t=self.out_curve, x=x_dist, y=y_dist),
                    anim_attrs(color, d=self.out_duration, a=0.),
                )
        finally:
            bg_canvas.clear()


def _escape_key_or_back_button(window: WindowBase, key, *args):
    # https://github.com/kivy/kivy/issues/9075
    return key in (27, 1073742106)


@asynccontextmanager
async def open_popup(
    popup: Widget, *, parent: WindowBase=Window, auto_dismiss: bool=True,
    transition: Transition=FadeTransition(), _cache: list[KXPopupBackground]=[],
) -> AsyncIterator[StatefulEvent]:
    async with AsyncExitStack() as stack:
        defer = stack.callback  # Because it works like Zig’s defer keyword.
        aenter = stack.enter_async_context

        bg = _cache.pop() if _cache else KXPopupBackground(); defer(_cache.append, bg)
        bg.opacity = 0
        bg.add_widget(popup); defer(bg.remove_widget, popup)
        parent.add_widget(bg); defer(parent.remove_widget, bg)
        await ak.sleep(0)  # Wait for the layout to complete
        bg.opacity = 1.0
        await aenter(transition(popup, bg, parent))
        if auto_dismiss:
            outside_touch_tracker = await aenter(ak.move_on_when(ak.event(bg, 'on_touch_down_outside_popup')))
            keyboard_tracker = await aenter(ak.move_on_when(ak.event(
                parent, 'on_keyboard', filter=_escape_key_or_back_button, stop_dispatching=True)))
        with bg.accept_inputs():
            ad_event = StatefulEvent()  # 'ad' stands for auto-dismiss
            yield ad_event
    if auto_dismiss:
        if outside_touch_tracker.finished:
            ad_event.fire('outside_touch')
        elif keyboard_tracker.finished:
            key = keyboard_tracker.result[1]
            ad_event.fire('escape_key' if key == 27 else 'back_button')
