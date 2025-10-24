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

If you leave the context manager empty, the `msgbox` will close immediately — which is probably not what you want.
To keep it open, you need to pause execution. For example:

```python
import asynckivy as ak

async with popup.open(msgbox):
    await ak.event(msgbox.ids.ok_button, 'on_release')
```

If your popup doesn’t include a button and you want it to close when the user touches outside of it, you can simply sleep forever:

```python
import asynckivy as ak

async with popup.open(msgbox):
    await ak.sleep_forever()
```
