'''
背景をぼかす例。

``kivy.uix.effectwidget`` にあるfragment shaderを拝借したもののあまりいい見た目にはならなかった。
なので https://github.com/kivy-garden/frostedglass のshaderを試す事を薦めます。
'''

from contextlib import asynccontextmanager

from kivy.graphics.texture import Texture
from kivy.graphics import Rectangle, Color, Fbo
from kivy.core.window import WindowBase
from kivy.core.window import Window, WindowBase
from kivy.uix.widget import Widget

import asynckivy as ak
from asynckivy import anim_attrs_abbr as anim_attrs


def capture_screen(target: WindowBase=Window, *, fragment_shader: str=None) -> Texture:
    w, h = target.system_size
    fbo = Fbo(size=(int(w), int(h)), with_stencilbuffer=True, fs=fragment_shader, clear_color=target.clearcolor)
    if not fbo.shader.success:
        raise Exception(f"Failed to set shader.")
    fbo.add(target.canvas)
    fbo.draw()
    fbo.remove(target.canvas)
    return fbo.texture


def apply_fragment_shader(target: Texture, fragment_shader: str) -> Texture:
    '''
    Applies a fragment shader to a texture and returns the result as a new texture.
    '''
    w, h = target.size
    fbo = Fbo(size=(int(w), int(h)), with_stencilbuffer=True, fs=fragment_shader)
    if not fbo.shader.success:
        raise Exception(f"Failed to set shader.")
    with fbo:
        Color()
        Rectangle(texture=target, pos=(0, 0), size=(w, h))
    fbo.draw()
    return fbo.texture


class BlurTransition:
    def __init__(self, *, in_duration=.1, out_duration=.1, blur_size=24.0):
        self.in_duration = in_duration
        self.out_duration = out_duration
        self.blur_size = blur_size

    @asynccontextmanager
    async def __call__(self, popup: Widget, bg, parent: WindowBase):
        bg_canvas = bg.canvas.before
        try:
            bg.opacity = 0
            dt = self.blur_size / 4.0 / bg.width
            blurred_screen = capture_screen(parent, fragment_shader=fs_horizontal_blur.format(dt))
            dt = self.blur_size / 4.0 / bg.height
            blurred_screen = apply_fragment_shader(blurred_screen, fs_vertical_blur.format(dt))
            with bg_canvas:
                Color()
                rect = Rectangle(texture=blurred_screen)
            with ak.sync_attr((bg, 'size'), (rect, 'size')):
                await anim_attrs(bg, d=self.in_duration, opacity=1.0)
                yield
                await anim_attrs(bg, d=self.out_duration, opacity=0.0)
        finally:
            bg.opacity = 1.0
            bg_canvas.clear()


fs_horizontal_blur = '''
$HEADER$

vec4 effect(vec4 color, sampler2D texture, vec2 tex_coords)
{{
    float dt = {};
    vec4 sum = vec4(0.0);
    sum += texture2D(texture, vec2(tex_coords.x - 4.0*dt, tex_coords.y))
                     * 0.077;
    sum += texture2D(texture, vec2(tex_coords.x - 3.0*dt, tex_coords.y))
                     * 0.077;
    sum += texture2D(texture, vec2(tex_coords.x - 2.0*dt, tex_coords.y))
                     * 0.077;
    sum += texture2D(texture, vec2(tex_coords.x - dt, tex_coords.y))
                     * 0.077;
    sum += texture2D(texture, vec2(tex_coords.x, tex_coords.y))
                     * 0.077;
    sum += texture2D(texture, vec2(tex_coords.x + dt, tex_coords.y))
                     * 0.077;
    sum += texture2D(texture, vec2(tex_coords.x + 2.0*dt, tex_coords.y))
                     * 0.077;
    sum += texture2D(texture, vec2(tex_coords.x + 3.0*dt, tex_coords.y))
                     * 0.077;
    sum += texture2D(texture, vec2(tex_coords.x + 4.0*dt, tex_coords.y))
                     * 0.077;
    return vec4(sum.xyz, color.w);
}}

void main (void){{
    vec4 normal_color = frag_color * texture2D(texture0, tex_coord0);
    vec4 effect_color = effect(normal_color, texture0, tex_coord0);
    gl_FragColor = effect_color;
}}
'''

fs_vertical_blur = '''
$HEADER$

vec4 effect(vec4 color, sampler2D texture, vec2 tex_coords)
{{
    float dt = {};
    vec4 sum = vec4(0.0);
    sum += texture2D(texture, vec2(tex_coords.x, tex_coords.y - 4.0*dt))
                     * 0.077;
    sum += texture2D(texture, vec2(tex_coords.x, tex_coords.y - 3.0*dt))
                     * 0.077;
    sum += texture2D(texture, vec2(tex_coords.x, tex_coords.y - 2.0*dt))
                     * 0.077;
    sum += texture2D(texture, vec2(tex_coords.x, tex_coords.y - dt))
                     * 0.077;
    sum += texture2D(texture, vec2(tex_coords.x, tex_coords.y))
                     * 0.077;
    sum += texture2D(texture, vec2(tex_coords.x, tex_coords.y + dt))
                     * 0.077;
    sum += texture2D(texture, vec2(tex_coords.x, tex_coords.y + 2.0*dt))
                     * 0.077;
    sum += texture2D(texture, vec2(tex_coords.x, tex_coords.y + 3.0*dt))
                     * 0.077;
    sum += texture2D(texture, vec2(tex_coords.x, tex_coords.y + 4.0*dt))
                     * 0.077;
    return vec4(sum.xyz, color.w);
}}

void main (void){{
    vec4 normal_color = frag_color * texture2D(texture0, tex_coord0);
    vec4 effect_color = effect(normal_color, texture0, tex_coord0);
    gl_FragColor = effect_color;
}}
'''


def main():
    from textwrap import dedent
    from kivy.lang import Builder
    from kivy.app import App
    from yes_no_popup import ask_yes_no_question

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
                        text: "start answering questions"
                        on_release: ak.managed_start(app.ask_questions())
                '''))

        async def ask_questions(self):
            questions = [
                "Do you like Python?",
                "Do you like Kivy?",
                "Do you like AsyncKivy?",
            ]
            for q in questions:
                answer = await ask_yes_no_question(q, transition=BlurTransition(blur_size=32.0))
                if answer is None:
                    answer = '<Unanswered>'
                print(q, '->', answer)
    TestApp().run()


if __name__ == '__main__':
    main()
