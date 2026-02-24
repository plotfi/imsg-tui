# imsg-tui
A console TUI for sending and receiving iMessages using @steipete's imsg tool

<img width="1877" height="1001" alt="Screenshot_20260222_093434" src="https://github.com/user-attachments/assets/a58caeb3-2a35-4b38-a146-2a3cf08cd08d" />


# Instalation
 
Easiest way to get things off the ground is intall on a Mac via homebrew (see https://github.com/steipete/homebrew-tap):

```
brew install steipete/tap/imsg
```

then

```
https://github.com/plotfi/imsg-tui
cd imsg-tui
python3 imsg-tui.py
```

You will need imsg to be in your path, or provide the path with `--imsg-path` 


Lastly, you will need to give permissions so that imsg can have access to your messages.
It will prompt for this; it is advised that you only give Terminal.app permissions and run this in tmux so that ssh-agent isnt able to directly have access.
