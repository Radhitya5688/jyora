document.querySelectorAll('form.searchbar').forEach(f=>f.addEventListener('submit',e=>{if(!f.querySelector('input').value.trim()){e.preventDefault();f.querySelector('input').focus()}}));
