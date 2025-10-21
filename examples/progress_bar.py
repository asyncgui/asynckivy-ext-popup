from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from kivy.core.window import Window, WindowBase
from kivy.lang import Builder
import kivy.properties as P
from kivy.uix.boxlayout import BoxLayout


import asynckivy as ak
from asynckivy_ext.popup import open, Transition, FadeTransition


Builder.load_string('''
<ProgressBarPopup>:
    padding: '20dp'
    spacing: '20dp'
    orientation: 'vertical'
    size_hint: .5, .5
    size_hint_min: self.minimum_size
    pos_hint: {'center_x': .5, 'center_y': .5}
    canvas.before:
        Color:
        Line:
            width: dp(2)
            rectangle: (*self.pos, *self.size, )
    Label:
        id: label
        size_hint_min: self.texture_size
    Widget:
        id: bar
        canvas:
            Color:
                rgb: .5, .5, .8
            Rectangle:
                size: self.width * root.progress, self.height
                pos: self.pos
            Color:
            Line:
                width: dp(2)
                rectangle: (*self.pos, *self.size, )
''')


class ProgressBarPopup(BoxLayout):
    goal_progress = P.NumericProperty()
    progress = P.NumericProperty()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        ak.smooth_attr((self, 'goal_progress'), (self, 'progress'), min_diff=0.01)



@asynccontextmanager
async def open_progress_bar_popup(
    text: str, *, progress=0.,
    window: WindowBase=Window, transition: Transition=FadeTransition(), _cache=[],
) -> AsyncIterator[ProgressBarPopup]:
    '''
    .. code-block::

        async with open_progress_bar_popup("Loading...") as popup:
            ...
    '''
    popup = _cache.pop() if _cache else ProgressBarPopup()
    try:
        popup.goal_progress = popup.progress = progress
        popup.ids.label.text = text
        async with open(popup, window=window, auto_dismiss=False, transition=transition):
            yield popup
    finally:
        _cache.append(popup)


def main():
    from textwrap import dedent
    import requests
    from kivy.lang import Builder
    from kivy.app import App

    class TestApp(App):
        def build(self):
            return Builder.load_string(dedent('''
                #:import ak asynckivy

                <Label>:
                    font_size: '24sp'

                AnchorLayout:
                    Button:
                        id: button
                        size_hint: .4, .2
                        size_hint_min: self.texture_size
                        padding: '10dp'
                        text: "open popup"
                        on_release: ak.managed_start(app.test_popup())
                '''))
        async def test_popup(self):
            from functools import partial
            from asynckivy.transition import fade_transition
            async with open_progress_bar_popup("Preparing...", transition=FadeTransition(in_duration=.2, out_duration=.5)) as popup:
                label = popup.ids.label
                ft = partial(fade_transition, label, duration=.3)
                await ak.sleep(1)

                async with ft():
                    label.text = "Sleeping..."
                popup.goal_progress = 0.3
                await ak.sleep(1)

                async with ft():
                    label.text = "Downloading..."
                popup.goal_progress = 0.6
                res = await ak.run_in_thread(lambda: requests.get("https://httpbin.org/delay/1"))

                async with ft():
                    label.text = res.json()['headers']['User-Agent']
                # popup.goal_progress = 0.9
                await ak.sleep(1)

                async with ft():
                    label.text = "Time is flowing backward"
                await ak.anim_attrs(popup, progress=.1)

                async with ft():
                    label.text = "Just kidding"
                popup.goal_progress = 1.0
                await ak.sleep(1.5)
    TestApp().run()


if __name__ == '__main__':
    main()
