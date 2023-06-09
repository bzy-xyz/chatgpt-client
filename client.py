'''
   Copyright 2023 Ben Z. Yuan (chatgpt-client@bzy-xyz.com)

   Licensed under the Apache License, Version 2.0 (the "License");
   you may not use this file except in compliance with the License.
   You may obtain a copy of the License at

       http://www.apache.org/licenses/LICENSE-2.0

   Unless required by applicable law or agreed to in writing, software
   distributed under the License is distributed on an "AS IS" BASIS,
   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
   See the License for the specific language governing permissions and
   limitations under the License.
'''

import wx
from models import ChatMessage, ConversationTree

import random
import os
import sys

import typing
import threading

import appdirs
import pathlib
import json

AppDirs = appdirs.AppDirs(appname="chatgpt-client",appauthor="bzy-xyz")

openai_api_key = os.getenv("OPENAI_API_KEY")
openai_api_org = os.getenv("OPENAI_API_ORG")

if openai_api_key:
    import openai
    openai.api_key = openai_api_key
    if openai_api_org:
        openai.organization = openai_api_org


def stringify_conversation(conv: ConversationTree) -> str:
    current_conv = conv.get_current_conversation()

    if len(current_conv) == 0:
        return ""

    ret = ""
    for i, msg in enumerate(current_conv):
        speaker_str = {
            'system': "System",
            'user': "You",
            'assistant': "ChatGPT",
        }.get(msg.role, msg.role.capitalize())
        if i == 0:
            ret += f"{i}: <{speaker_str}>\n"
        else:
            branch_width = conv.get_branch_width(i-1)
            child_idx = current_conv[i-1].current_child_idx
            ret += f"{i}: <({child_idx+1}/{branch_width}) {speaker_str}>\n"
        ret += msg.content
        if i < len(current_conv):
            ret += f"\n{'-'*50}\n"
    return ret

def _get_next_completion_thread(conv: ConversationTree, and_then: typing.Callable, truncate_before: int | None):
    if openai_api_key:
        curr_conv = conv.get_current_conversation_as_dicts()
        if truncate_before != None:
            curr_conv = curr_conv[:truncate_before]
        test_model = "gpt-3.5-turbo"
        completion = openai.ChatCompletion.create(
            model=test_model,
            messages=curr_conv
        )
        resp = completion['choices'][0]['message']
    else:
        resp = {'role': 'assistant', 'content': f'As an AI language model, simulated response {random.randint(0, 2**32)}'}

    and_then(resp)

def _get_title_for_conversation_thread(conv: ConversationTree, and_then: typing.Callable):
    if openai_api_key:
        curr_conv = conv.get_current_conversation_as_dicts()
        if len(curr_conv) >= 3:
            test_model = "gpt-3.5-turbo"
            completion = openai.ChatCompletion.create(
                model=test_model,
                messages=[
                    {'role': 'system', 'content': 'Provide a short title, less than 5 words whenever possible, summarizing a user-submitted conversation between a user and an AI model, provided in JSON form. Avoid using the user\'s query verbatim in your title. Respond to user queries with the title you are providing, without other prefixes or suffixes.'},
                    {'role': 'user', 'content': str(curr_conv)}
                ]
            )
            resp = completion['choices'][0]['message']
            and_then(resp)

def get_next_completion(conv: ConversationTree, and_then: typing.Callable, truncate_before: int | None = None):
    thread = threading.Thread(target=_get_next_completion_thread, args=(conv, and_then, truncate_before))
    thread.start()

def get_title_for_conversation_thread(conv: ConversationTree, and_then: typing.Callable):
    thread = threading.Thread(target=_get_title_for_conversation_thread, args=(conv, and_then))
    thread.start()

class ChatClient(wx.Frame):
    def __init__(self, parent, title):
        super(ChatClient, self).__init__(parent, title=title, size=(800, 600))

        self.conversations = []
        self.current_conversation = None
        self.current_conversation_idx = None

        # create left pane
        self.left_panel = wx.Panel(self)
        left_sizer = wx.BoxSizer(wx.VERTICAL)
        self.left_list = wx.ListBox(self.left_panel, style=wx.LB_SINGLE | wx.LB_ALWAYS_SB)
        self.left_list.Bind(wx.EVT_LISTBOX, self.on_conversation_list_selected)
        self.left_button = wx.Button(self.left_panel, label="New conversation")
        self.left_button.Bind(wx.EVT_BUTTON, self.create_conversation)
        left_sizer.Add(self.left_list, proportion=1, flag=wx.EXPAND | wx.ALL, border=10)
        left_sizer.Add(self.left_button, flag=wx.EXPAND | wx.ALL, border=10)
        self.left_panel.SetSizer(left_sizer)

        # create right pane
        self.right_panel = wx.Panel(self)
        right_sizer = wx.BoxSizer(wx.VERTICAL)
        self.right_text = wx.TextCtrl(self.right_panel, style=wx.TE_MULTILINE|wx.TE_READONLY|wx.TE_RICH2, value="Press 'New conversation' to create a new conversation.")
        self.right_text.SetMinSize((300, 300))
        font = wx.Font(wx.FontInfo(12))
        if not font.SetFaceName("Courier New"):
            font.SetFamily(wx.FONTFAMILY_TELETYPE)
        self.right_text.SetFont(font)
        self.input_text = wx.TextCtrl(self.right_panel, size=(-1, 60), style=wx.TE_MULTILINE|wx.TE_PROCESS_ENTER)
        self.input_text.SetFont(font)
        self.right_button = wx.Button(self.right_panel, label="Send")
        self.right_button.Bind(wx.EVT_BUTTON, self.on_send_pressed)
        right_sizer.Add(self.right_text, proportion=1, flag=wx.EXPAND | wx.ALL, border=10)
        right_sizer.Add(wx.StaticLine(self.right_panel), flag=wx.EXPAND | wx.ALL, border=10)
        right_sizer.Add(self.input_text, flag=wx.EXPAND | wx.ALL, border=10)
        right_sizer.Add(self.right_button, flag=wx.ALL, border=10)
        self.right_panel.SetSizer(right_sizer)

        # create main sizer and add panes
        main_sizer = wx.BoxSizer(wx.HORIZONTAL)
        main_sizer.Add(self.left_panel, proportion=1, flag=wx.EXPAND | wx.ALL, border=10)
        main_sizer.Add(self.right_panel, proportion=3, flag=wx.EXPAND | wx.ALL, border=10)
        self.SetSizer(main_sizer)

        self.load()

        self.Bind(wx.EVT_CLOSE, self.on_close)

        # show the window
        self.Show()

    def on_close(self, event: wx.CloseEvent):
        self.save()
        event.Skip()

    def save(self):
        pathlib.Path(AppDirs.user_state_dir).mkdir(parents=True, exist_ok=True)
        with open(pathlib.Path(AppDirs.user_state_dir) / 'state.dat', 'w') as f:
            json.dump({
                'conversations': [[a[0], a[1].serialize()] for a in self.conversations],
                'current_conv_idx': self.current_conversation_idx
            }, f)

    def load(self):
        try:
            with open(pathlib.Path(AppDirs.user_state_dir) / 'state.dat') as f:
                dat = json.load(f)
                self.conversations = [[a[0], ConversationTree.unserialize(a[1])] for a in dat['conversations']]
                self.current_conversation_idx = dat['current_conv_idx']
                self.current_conversation = self.conversations[self.current_conversation_idx][1]
                self.refresh_conversation_list()
                self.refresh_conversation_detail()
        except OSError:
            pass
        except json.JSONDecodeError as e:
            print(repr(e), file=sys.stderr)

    def start_thinking_state(self):
        self.right_text.AppendText("\nChatGPT is thinking...")
        self.right_button.Disable()
        self.left_list.Disable()
        self.left_button.Disable()

    def stop_thinking_state(self):
        self.right_button.Enable()
        self.left_list.Enable()
        self.left_button.Enable()

    def create_conversation(self, event):
        new_conv = ConversationTree()
        new_conv.add_message("system", "You are a helpful assistant.")
        self.conversations.append([f"New conversation", new_conv])
        self.current_conversation = new_conv
        self.current_conversation_idx = len(self.conversations) - 1
        self.refresh_conversation_list()
        self.refresh_conversation_detail()

    def refresh_conversation_list(self):
        conversation_titles = []
        current_idx = 0
        for i, c in enumerate(reversed(self.conversations)):
            title, conv = c
            conversation_titles.append(title)
            if self.current_conversation == conv:
                current_idx = i
        self.left_list.Set(conversation_titles)
        if len(conversation_titles) > 0:
            self.left_list.SetSelection(current_idx)

    def on_send_pressed(self, event):
        if self.current_conversation == None:
            self.create_conversation(None)
        self.parse_command(self.input_text.GetValue())
        self.input_text.Clear()

    def on_enter_pressed(self, event: wx.Event):
        if wx.GetKeyState(wx.WXK_SHIFT):
            event.Skip()
        else:
            self.on_send_pressed(event)

    def on_conversation_list_selected(self, event):
        selection = self.left_list.GetSelection()
        if selection != wx.NOT_FOUND:
            self.current_conversation_idx = len(self.conversations) - 1 - selection
            self.current_conversation = self.conversations[self.current_conversation_idx][1]
            self.refresh_conversation_detail()

    def refresh_conversation_detail(self):
        self.right_text.Clear()
        self.right_text.AppendText(stringify_conversation(self.current_conversation))

    def add_to_conversation(self, role, content):
        self.current_conversation.add_message(role, content)
        self.refresh_conversation_detail()
        if self.conversations[self.current_conversation_idx][0] == "New conversation" and role == "assistant":
            self.conversations[self.current_conversation_idx][0] = "Retrieving title..."
            self.refresh_conversation_list()
            self.get_title_for_conversation(self.current_conversation_idx)

    def add_to_branch(self, sibling_level, role, content):
        if sibling_level >= 1 and sibling_level < len(self.current_conversation.get_current_conversation()):
            self.current_conversation.add_message(role, content, sibling_level - 1)
            self.refresh_conversation_detail()
            return True
        else:
            self.right_text.AppendText(f"\n\nrequested sibling level outside range (1 - {len(self.current_conversation.get_current_conversation())})")
            return False

    def switch_branch(self, msg_idx, branch_idx):
        try:
            self.current_conversation.change_branch(msg_idx - 1, branch_idx - 1)
            self.refresh_conversation_detail()
            return True
        except Exception as e:
            self.right_text.AppendText(f"\n\n{str(e)}")
            return False

    def role_at_level(self, msg_idx):
        curr_conv = self.current_conversation.get_current_conversation()
        if msg_idx >= 0 and msg_idx <= len(curr_conv):
            return curr_conv[msg_idx].role
        else:
            return '?'

    def new_branch(self, sibling_level, content):
        if sibling_level >= 1 and sibling_level < len(self.current_conversation.get_current_conversation()):
            if self.role_at_level(sibling_level) == 'assistant':
                self.start_thinking_state()
                def post_completion(resp):
                    wx.CallAfter(self.add_to_branch, sibling_level, resp['role'], resp['content'])
                    wx.CallAfter(self.stop_thinking_state)
                get_next_completion(self.current_conversation, post_completion, sibling_level)
            else:
                if self.add_to_branch(sibling_level, 'user', content):
                    self.start_thinking_state()
                    def post_completion(resp):
                        wx.CallAfter(self.add_to_conversation, resp['role'], resp['content'])
                        wx.CallAfter(self.stop_thinking_state)
                    get_next_completion(self.current_conversation, post_completion)
        else:
            self.right_text.AppendText(f"\n\nrequested sibling level for new-branch outside range (1 - {len(self.current_conversation.get_current_conversation())})")
            return False

    def new_child(self, input_string):
        self.add_to_conversation("user", input_string)
        self.start_thinking_state()
        def post_completion(resp):
            wx.CallAfter(self.add_to_conversation, resp['role'], resp['content'])
            wx.CallAfter(self.stop_thinking_state)
        get_next_completion(self.current_conversation, post_completion)

    def get_title_for_conversation(self, idx):
        def post_completion(resp):
            self.conversations[idx][0] = resp['content']
            self.refresh_conversation_list()
        get_title_for_conversation_thread(self.conversations[idx][1], post_completion)

    def unrecognized_command(self):
        self.right_text.AppendText(f"\n\nunrecognized / command, try one of these instead:\n/sw a b -- switches level a message to alternative b\n/nb n str -- creates a new response at level n (str ignored when replacing ChatGPT resps)")

    def parse_command(self, input_string):
        if input_string.startswith('/sw'):
            parts = input_string.split()
            if len(parts) == 3:
                a, b = map(int, parts[1:])
                self.switch_branch(a, b)
                return
            else:
                self.unrecognized_command()
                return
        elif input_string.startswith('/nb'):
            parts = input_string.split(maxsplit=2)
            if len(parts) == 3:
                a, txt = int(parts[1]), parts[2]
                self.new_branch(a, txt)
                return
            elif len(parts) == 2:
                a = int(parts[1])
                if self.role_at_level(a) == 'assistant':
                    self.new_branch(a, None)
                else:
                    self.right_text.AppendText(f"\n\nnew-branch for level {a} also requires a prompt (e.g. /nb {a} Hello, world!)")
            else:
                self.unrecognized_command()
                return
        elif input_string.startswith('/'):
            self.unrecognized_command()
            return
        else:
            self.new_child(input_string)
            return

if __name__ == '__main__':
    app = wx.App()
    ChatClient(None, title='Chat Client')
    app.MainLoop()
