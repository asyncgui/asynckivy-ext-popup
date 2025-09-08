import itertools
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator
from kivy.graphics import Line, Color, InstructionGroup

from kivy.core.window import Window, WindowBase
from kivy.lang import Builder
from kivy.factory import Factory


import asynckivy as ak
from asynckivy_ext.popup import open_popup, Transition, SlideTransition


Builder.load_string('''
<ProgressSpinnerPopup@BoxLayout>:
    padding: '20dp'
    spacing: '20dp'
    orientation: 'vertical'
    size_hint: .5, .5
    size_hint_min: self.minimum_size
    canvas.before:
        Color:
        Line:
            width: dp(2)
            rectangle: (*self.pos, *self.size, )
    Label:
        id: label
        size_hint_min: self.texture_size
    RelativeLayout:
        id: spinnner_area
    Button:
        id: cancel_button
        size_hint: .3, .5
        size_hint_min: self.texture_size
        pos_hint: {'center_x': .5}
        text: "Cancel"
''')
ProgressSpinnerPopup = Factory.get('ProgressSpinnerPopup')


async def progress_spinner(
        *, draw_target: InstructionGroup, center, radius, line_width=3, color=(1, 1, 1, 1, ), min_arc_angle=40,
        speed=1.0):

    BS = 40.0  # base speed (in degrees)
    AS = 360.0 - min_arc_angle * 2
    get_next_start = itertools.accumulate(itertools.cycle((BS, BS, BS + AS, BS, )), initial=0).__next__
    get_next_stop = itertools.accumulate(itertools.cycle((BS + AS, BS, BS, BS, )), initial=min_arc_angle).__next__
    duration = 0.4 / speed
    cur_start = get_next_start()
    cur_stop = get_next_stop()
    draw_target.add(color_inst := Color(*color))
    draw_target.add(line_inst := Line(width=line_width))
    try:
        line_inst.circle = (*center, radius, cur_start, cur_stop)
        while True:
            next_start = get_next_start()
            next_stop = get_next_stop()
            async for start, stop in ak.interpolate_seq((cur_start, cur_stop), (next_start, next_stop), duration=duration):
                line_inst.circle = (*center, radius, start, stop)
            cur_start = next_start
            cur_stop = next_stop
    finally:
        draw_target.remove(line_inst)
        draw_target.remove(color_inst)


@asynccontextmanager
async def open_progress_spinner_popup(
    text: str, *, window: WindowBase=Window, transition: Transition=SlideTransition(), _cache=[],
) -> AsyncIterator[ProgressSpinnerPopup]:
    '''
    .. code-block::

        async with open_progress_spinner_popup("Loading...") as popup:
            ...
    '''
    popup = _cache.pop() if _cache else ProgressSpinnerPopup()
    try:
        popup.ids.label.text = text
        spinner_area = popup.ids.spinnner_area
        async with (
            open_popup(popup, window=window, auto_dismiss=False, transition=transition),
            ak.move_on_when(ak.event(popup.ids.cancel_button, 'on_release')) as cancel_tracker,
            ak.run_as_daemon(progress_spinner(
                draw_target=spinner_area.canvas,
                center=(spinner_area.width / 2, spinner_area.height / 2),
                radius=min(spinner_area.size) / 2.,
            )),
        ):
            yield popup
    finally:
        popup.cancelled = cancel_tracker.finished
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
            from message_box import message_box
            async with open_progress_spinner_popup("Preparing...") as popup:
                label = popup.ids.label
                ft = partial(fade_transition, label, duration=.3)
                await ak.sleep(1)

                async with ft():
                    label.text = "Sleeping..."
                await ak.sleep(1)

                async with ft():
                    label.text = "Downloading..."
                res = await ak.run_in_thread(lambda: requests.get("https://httpbin.org/delay/1"))
            await message_box("Cancelled" if popup.cancelled else res.json()['headers']['User-Agent'])
    TestApp().run()


if __name__ == '__main__':
    main()
