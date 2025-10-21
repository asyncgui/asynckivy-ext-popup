__all__ = (
    'open', 'Transition', 'NoTransition', 'FadeTransition', 'SlideTransition',
)

from typing import TypeAlias, Literal
from functools import partial
from collections.abc import Callable, AsyncIterator
from contextlib import AsyncExitStack, contextmanager, asynccontextmanager, AbstractAsyncContextManager

from kivy.graphics import Translate, Rectangle, Color
from kivy.core.window import Window, WindowBase
from kivy.uix.widget import Widget
from kivy.uix.floatlayout import FloatLayout


import asynckivy as ak
from asynckivy import anim_attrs_abbr as anim_attrs


_default_bgcolor = (0., 0., 0., .8)
Transition: TypeAlias = Callable[[Widget, 'KXPopupParent', WindowBase], AbstractAsyncContextManager]
'''
Defines how a popup appears and disappears.
'''


class KXPopupParent(FloatLayout):
    '''(internal)'''
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._block_inputs = True
        self.on_auto_dismiss: Callable[[str], None] = None

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
        if c.collide_point(*touch.opos):  # FloatLayout is not a relative-type widget, no need for translation
            c.dispatch('on_touch_down', touch)
        elif (f := self.on_auto_dismiss) is not None:
            f('outside_touch')
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
    async def __call__(self, popup: Widget, parent: KXPopupParent, window: WindowBase):
        bg_canvas = parent.canvas.before
        try:
            with bg_canvas:
                Color(*self.background_color)
                rect = Rectangle()
            with ak.sync_attr((parent, 'size'), (rect, 'size')):
                yield
        finally:
            bg_canvas.clear()


class FadeTransition:
    def __init__(self, *, in_duration=.1, out_duration=.1, background_color=_default_bgcolor):
        self.in_duration = in_duration
        self.out_duration = out_duration
        self.background_color = background_color

    @asynccontextmanager
    async def __call__(self, popup: Widget, parent: KXPopupParent, window: WindowBase):
        bg_canvas = parent.canvas.before
        try:
            parent.opacity = 0
            await ak.sleep(0)
            with bg_canvas:
                Color(*self.background_color)
                rect = Rectangle()
            with ak.sync_attr((parent, 'size'), (rect, 'size')):
                await anim_attrs(parent, d=self.in_duration, opacity=1.0)
                yield
                await anim_attrs(parent, d=self.out_duration, opacity=0.0)
        finally:
            bg_canvas.clear()


class SlideTransition:
    '''
    Slides the popup in and out from a given direction.

    You cannot specify the out-direction, it is always the opposite of the in-direction.
    '''
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
    async def __call__(self, popup: Widget, parent: KXPopupParent, window: WindowBase):
        bg_canvas = parent.canvas.before
        parent.opacity = 0.
        await ak.sleep(0)
        try:
            bg_alpha = self.background_color[3]
            with bg_canvas:
                color = Color(*self.background_color[:3], 0.)
                rect = Rectangle()
            with (
                ak.sync_attr((parent, 'size'), (rect, 'size')),
                ak.transform(popup, use_outer_canvas=True) as ig,
            ):
                x_dist = y_dist = 0.
                match self.in_direction:
                    case 'down':
                        y_dist = parent.height - popup.y
                    case 'up':
                        y_dist = -popup.top
                    case 'left':
                        x_dist = parent.width - popup.x
                    case 'right':
                        x_dist = -popup.right
                    case _:
                        raise ValueError(f'Invalid in_direction: {self.in_direction}')
                ig.add(mat := Translate(x_dist, y_dist))
                parent.opacity = 1.
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


def _escape_key_or_back_button(on_auto_dismiss, window, key, *args):
    # https://github.com/kivy/kivy/issues/9075
    if key == 27:
        on_auto_dismiss('escape_key')
        return True
    elif key == 1073742106:
        on_auto_dismiss('back_button')
        return True


@asynccontextmanager
async def open(
    popup: Widget, *, window: WindowBase=Window, auto_dismiss=True,
    transition: Transition=FadeTransition(), _cache: list[KXPopupParent]=[],
) -> AsyncIterator[ak.StatefulEvent]:
    '''
    Returns an async context manager that opens a popup.

    :param popup: The popup widget to open.
    :param window: The window to open the popup in.
    :param auto_dismiss: Whether to dismiss the popup when the user clicks outside it or presses
                         the escape key or back button.
    :param transition: The transition to use when the popup appears and disappears.

    You can tell if the popup was auto-dismissed and what caused it as follows:

    .. code-block::

        async with open(popup) as auto_dismiss_event:
            ...
        if auto_dismiss_event.is_fired:
            print("The popup was auto-dismissed")

            # 'outside_touch', 'escape_key' or 'back_button'
            the_cause_of_auto_dismiss = auto_dismiss_event.params[0][0]
    '''
    async with AsyncExitStack() as stack:
        defer = stack.callback  # Because it works like the defer keyword from other languages.

        parent = _cache.pop() if _cache else KXPopupParent(); defer(_cache.append, parent)
        parent.on_auto_dismiss = None
        parent.add_widget(popup); defer(parent.remove_widget, popup)
        window.add_widget(parent); defer(window.remove_widget, parent)

        await stack.enter_async_context(transition(popup, parent, window))
        ad_event = ak.StatefulEvent()  # 'ad' stands for 'auto dismiss'
        if auto_dismiss:
            bind_id = window.fbind("on_keyboard", partial(_escape_key_or_back_button, ad_event.fire))
            defer(window.unbind_uid, "on_keyboard", bind_id)
            parent.on_auto_dismiss = ad_event.fire
            await stack.enter_async_context(ak.move_on_when(ad_event.wait()))
        with parent.accept_inputs():
            yield ad_event
