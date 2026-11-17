"""Small rounded Tk controls; no additional UI runtime required."""
import tkinter as tk

BLUE = '#0078D4'
BG = '#F3F7FC'
INK = '#172B4D'


class RoundButton(tk.Canvas):
    def __init__(self, master, text, command, primary=False, width=120, **kwargs):
        super().__init__(master, width=width, height=40, bg=master.cget('bg'),
                         highlightthickness=0, bd=0, takefocus=1, **kwargs)
        self.text, self.command, self.primary = text, command, primary
        self.disabled = False
        self.hover = False
        self.bind('<Configure>', lambda e:self.draw())
        self.bind('<Enter>', lambda e:self.roll(True))
        self.bind('<Leave>', lambda e:self.roll(False))
        self.bind('<Button-1>', lambda e:self.invoke())
        self.bind('<Return>', lambda e:self.invoke())
        self.bind('<space>', lambda e:self.invoke())
        self.bind('<FocusIn>', lambda e:self.draw())
        self.bind('<FocusOut>', lambda e:self.draw())
        self.draw()

    def configure(self, cnf=None, **kwargs):
        if 'state' in kwargs:
            self.disabled = kwargs.pop('state') == 'disabled'
            super().configure(takefocus=0 if self.disabled else 1)
        if 'text' in kwargs:
            self.text = kwargs.pop('text')
        super().configure(cnf, **kwargs)
        if hasattr(self,'text'):
            self.draw()

    def roll(self, hover):
        self.hover = hover
        self.draw()

    def invoke(self):
        if not self.disabled:
            self.focus_set()
            self.command()

    def draw(self):
        self.delete('all')
        w = max(self.winfo_width(), int(self.cget('width')))
        fill = ('#E5ECF4' if self.disabled else
                ('#0067B8' if self.hover else BLUE) if self.primary else
                ('#DCEEFF' if self.hover else '#EAF3FD'))
        fg = '#8797AA' if self.disabled else ('white' if self.primary else '#0067B8')
        self.create_polygon(12,2,w-12,2,w-2,2,w-2,12,w-2,28,w-2,38,w-12,38,
                            12,38,2,38,2,28,2,12,2,2,
                            smooth=True,fill=fill,outline=BLUE if self.focus_get()==self else fill)
        self.create_text(w/2,20,text=self.text,fill=fg,font=('Microsoft YaHei UI',10,'bold'))
        super().configure(cursor='arrow' if self.disabled else 'hand2')


class Card(tk.Canvas):
    def __init__(self, master, **kwargs):
        super().__init__(master,bg=master.cget('bg'),highlightthickness=0,bd=0,**kwargs)
        self.body = tk.Frame(self,bg='white')
        self.window = self.create_window(18,16,window=self.body,anchor='nw')
        self.bind('<Configure>',self.layout)

    def layout(self, event):
        w,h=event.width,event.height
        self.delete('surface')
        self.create_polygon(20,1,w-20,1,w-1,1,w-1,20,w-1,h-20,w-1,h-1,
                            w-20,h-1,20,h-1,1,h-1,1,h-20,1,20,1,1,
                            smooth=True,fill='white',outline='#E1EAF5',tags='surface')
        self.tag_lower('surface')
        self.itemconfigure(self.window,width=max(1,w-36),height=max(1,h-32))
