# asynckivy_ext.popup

- Helps you create your own popup widgets.
- Unlike `kivy.uix.modalview`, you have full control over the appearance and transitions.

## Installation

```
pip install git+https://github.com/asyncgui/asynckivy-ext-popup.git
```

## Usage

### 1. Design your popup widget

```yaml
<MessageBox@BoxLayout>:
    pos_hint: {'center': (.5, .5), }  # Center the popup, if desired
    Label:
        id: label
    Button:
        id: ok_button
        text: 'OK'
```

### 2. Pass an instance of your popup to `popup.open()`

```python
from asynckivy_ext import popup

msgbox = MessageBox()
msgbox.ids.label.text = 'Hello'

async with popup.open(msgbox):
    ...
```

If you leave the with-block empty, the `msgbox` will be dismissed immediately — which is probably not what you want.
To keep it open, you need to pause the execution of the coroutine. For example:

```python
import asynckivy as ak

async with popup.open(msgbox):
    await ak.event(msgbox.ids.ok_button, 'on_release')
```

If your popup doesn’t have a button that dismiss it, it's okay to sleep forever inside the with-block.
The user can still dismiss the popup by touching outside of it or by pressing the escape key or the Android back button — unless `auto_dismiss` is set to False.

```python
import asynckivy as ak

async with popup.open(msgbox):
    await ak.sleep_forever()
```
