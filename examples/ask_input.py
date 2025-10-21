from collections.abc import Awaitable

from kivy.core.window import Window, WindowBase
from kivy.lang import Builder
from kivy.factory import Factory
from kivy.uix.textinput import TextInput

import asynckivy as ak
from asynckivy_ext.popup import open, Transition, FadeTransition


Builder.load_string('''
<PromptPopup@BoxLayout>:
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
    TextInput:
        id: textinput
        multiline: False
        size_hint_y: None
        height: self.font_size * 2.0
    BoxLayout:
        spacing: '10dp'
        Button:
            id: cancel_button
            size_hint_min: self.texture_size
        Button:
            id: ok_button
            size_hint_min: self.texture_size
''')
PromptPopup = Factory.get('PromptPopup')


async def ask_input(
    message: str, *, window: WindowBase=Window, ok_text='OK', cancel_text='Cancel',
    input_filter=TextInput.input_filter.defaultvalue, input_type=TextInput.input_type.defaultvalue,
    transition: Transition=FadeTransition(), auto_dismiss=True, _cache=[],
) -> Awaitable[None | str]:
    '''
    Asks input using a popup dialog.

    .. code-block::

        age = await ask_input("How old are you?", input_filter='int', input_type='number')

    :return: None if the popup is auto-dismissed or the cancel button is tapped,
    '''
    popup = _cache.pop() if _cache else PromptPopup()
    try:
        ids = popup.ids
        ids.label.text = message
        ids.ok_button.text = ok_text
        ids.cancel_button.text = cancel_text
        ti = ids.textinput
        ti.text = ''
        ti.input_filter = input_filter
        ti.input_type = input_type
        ti.focus = True
        async with open(popup, window=window, auto_dismiss=auto_dismiss, transition=transition) as ad_event:
            tasks = await ak.wait_any(
                ak.event(ti, 'on_text_validate'),
                ak.event(ids.ok_button, 'on_release'),
                ak.event(ids.cancel_button, 'on_release'),
            )
        if ad_event.is_fired or tasks[2].finished:
            return None
        return ti.text
    finally:
        _cache.append(popup)


def main():
    from textwrap import dedent
    from kivy.lang import Builder
    from kivy.app import App

    class TestApp(App):
        def build(self):
            return Builder.load_string(dedent('''
                #:import ak asynckivy

                <Label,TextInput>:
                    font_size: '24sp'

                AnchorLayout:
                    Button:
                        id: button
                        size_hint: .4, .2
                        size_hint_min: self.texture_size
                        padding: '10dp'
                        text: "start answering questions"
                        on_release: ak.managed_start(app.ask_questions())
                '''))

        async def ask_questions(self):
            q = "What's your name?"
            name = await ask_input(q)
            if name is None:
                name = '<no answer>'
            print(q, '->', name)

            q = "How old are you?"
            age = await ask_input(q, input_filter='int', input_type='number')
            if age is None:
                age = '<no answer>'
            print(q, '->', age)

            q = "When is your birthday?"
            birthday = await ask_input(q, input_type='datetime')  # 'datetime' seems not to work on Desktop
            if birthday is None:
                birthday = '<no answer>'
            print(q, '->', birthday)
    TestApp().run()


if __name__ == '__main__':
    main()
