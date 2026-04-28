
const API = "http://127.0.0.1:8000";

document.addEventListener('DOMContentLoaded',()=>{
    loadchat();
    autoResizeTextarea();
    document.getElementById('msg-input').addEventListener('keydown', e => {
      if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendmessage(); }
    });
});

let currentchatid = null;

async function api(path,opt={}){
    const res = await fetch(API + path,opt);
    
    if(!res.ok){
        const err = await res.json().catch(()=>({detail:res.statusText}));
        throw new Error(err.detail || "request Failed");
    }

    return res.json()
}


function switchtab(tab){
    document.querySelectorAll('.tabbtn').forEach((btn,i)=>{
        btn.classList.toggle('active',(i===0 && tab==='pdf') || (i===1 && tab==='url'))
    });

    document.getElementById('tab-pdf').classList.toggle('active',(tab==='pdf'));
    document.getElementById('tab-url').classList.toggle('active',(tab==='url'));
}


function openchatmodal(){
    document.getElementById('chatmodal').classList.add('open');
}


function closechatmodal(){
    document.getElementById('chatmodal').classList.remove('open');
}



async function createchat(){
    const name = document.getElementById('chatname').value.trim();
    const platform = document.getElementById('platformname').value;
    console.log("hello i am here");
    // if(!name){
    //     return;
    // }
    try {
        const res = await api('/api/chats',{
            method : 'POST',
            headers : {'Content-Type': 'application/json'},
            body : JSON.stringify({chat_name:name,platform})
        }) ;
        console.log(res,typeof(res));
        closechatmodal(); 
        await loadchat(); 
        await selectchat(res.chat_id);
        document.getElementById('chatname').value = '';   
    } catch (e) {
        console.log(e.message);
    }
}

async function loadchat(){
    try {
        chats = await api('/api/chats');
        renderchatlist(chats);
    } catch (e) {
        console.log(e.message);
    }
}

async function renderchatlist(chats){
    const list = document.getElementById('list-of-chats');
    const emptylist = document.getElementById('emptylist');

    list.querySelectorAll('.chat-item').forEach(el => el.remove());

    if (!chats.length) {
      emptylist.style.display = '';
      return;
    }
    emptylist.style.display = 'none';

    chats.forEach(chat=>{
        const item = document.createElement('div');
        item.className = 'chat-item';
        item.id = chat.id

        item.innerHTML=`
        <div class="chat-item-info" onclick="selectchat(${chat.id})">
            <div class="chat-item-name" id="chat-name-${chat.id}">${chat.chat_name}</div>
            <div class="chat-item-meta">${chat.updated_at}</div>
        </div>
        <span class="badge badge-${chat.platform.toLowerCase()}">${chat.platform}</span>
        <button class="delete-btn">🗑️</button>
        `;
        list.appendChild(item);
    })

}

async function selectchat(chatid){
    console.log('chat-selected');
    document.querySelectorAll('.chat-item').forEach((item)=>{
        item.classList.remove('active');
    })
    document.getElementById(chatid).classList.add('active');

    currentchatid = chatid;

    document.getElementById('document-upload').disabled = false;

    const subtitle = document.getElementById('subtitle');
    const value = document.getElementById(`chat-name-${chatid}`).textContent;
    subtitle.innerHTML=`${value}`;

    // loadmessages(chatid);
    const input = document.getElementById('msg-input');
    input.disabled=false;
    input.placeholder = "Type Your Prompt here..."
    document.getElementById('send-btn').disabled=false;

    await loadmessages(chatid);

}


async function loadmessages(chatid){
    clearmessages()
    showwelcome(false)
    try {
        const msgs = await api(`/api/chats/${chatid}/messages`);
        msgs.forEach(m=>appendmessages(m.role,m.content,m.timestamp,m.source));
    } catch (e) {
        console.log(e.message)
    }
}


function clearmessages(){
    const area = document.getElementById('message-area');
    area.querySelectorAll('.msg-wrap').forEach(el=>el.remove());
}

function showwelcome(flag){
    if(flag === false){
        document.getElementById('welcome').style.display='none';
    }
    else{
        document.getElementById('welcome').style.display='';
    }
}

function appendmessages(role,content,time,source){
    const area = document.getElementById('message-area');

    const wrap = document.createElement('div');
    wrap.className = `msg-wrap ${role}`;
    
    const bubble = document.createElement('div');
    bubble.className = `msg-bubble ${role}`;

    if(role==='assistant'){
        bubble.innerHTML = marked.parse(content);
    }
    else{
        bubble.innerText = content
    }

    wrap.appendChild(bubble);

    if(source){
        const src = document.createElement('div');
        src.className = 'msg-src';
        src.textContent = '📎 ' + source;
        wrap.appendChild(src);

    }

    if(time){
        const t = document.createElement('div');
        t.className = 'msg-time';
        t.textContent = '🕐' + time;
        wrap.appendChild(t);

    }

    area.appendChild(wrap);
    area.scrollTop = area.scrollHeight;
}


async function sendmessage(){
    const input = document.getElementById('msg-input')
    const text = input.value.trim();
    const send = document.getElementById('send-btn');

    if(!text){
        return;
    }
    input.value = ''
    input.style.height = 'auto';

    appendmessages('user',text,nowtime());
    input.disabled = true
    send.disabled = true

    try {

        const res = await api(`/api/chats/${currentchatid}/message`,{
            method:'POST',
            headers : {'Content-Type':'application/json'},
            body : JSON.stringify({message : text}),
    })
    
    res.responses.forEach(r=>{appendmessages('assistant',r,nowtime())});
    } catch (e) {
        console.log(e.message); 
    }
    finally{
        input.disabled = false;
        send.disabled = false;
    }

}

function nowtime(){
    const now = new Date();
    return now.toLocaleTimeString([],{timeStyle:'short'})
}

let selectedfile = null

document.getElementById('pdf-file').addEventListener('change',(e)=>{
    selectedfile = e.target.files[0];
    console.log(selectedfile.name);
    document.getElementById('file-name').textContent = selectedfile ? selectedfile.name : '';
    document.getElementById('upload-pdf-btn').disabled = !selectedfile;
})

function openuploadmodel(){
    document.getElementById('uploadmodal').classList.add('open');
}

function closeuploadmodel(){
    document.getElementById('uploadmodal').classList.remove('open');
}

async function uploadpdf(){
    console.log("file selected is ", selectedfile.name);
    const formData = new FormData();
    formData.append('file',selectedfile);
    closeuploadmodel();
    

    try {
        const res = await api(`/api/chats/${currentchatid}/uploadpdf`,{
            method:'POST',
            body : formData
        });
        appendmessages('user',res.user_message,nowtime(),selectedfile.name);
        appendmessages('assistant',res.assistant_message,nowtime());
    } catch (e) {
        console.log(e.message)
    }
    finally{
    selectedfile = null;
    document.getElementById('file-name').textContent = '';
    }
}

async function submiturl() {
    const url = document.getElementById('yt-url').value.trim();
    closeuploadmodel();
    try {
      const res = await api(`/api/chats/${currentchatid}/upload-url`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ chat_id: currentchatid, url })
      });
      console.log("url submitted")
    } catch(e) {console.log(e.message) }
    finally {
      document.getElementById('yt-url').value = '';
    }
  }




