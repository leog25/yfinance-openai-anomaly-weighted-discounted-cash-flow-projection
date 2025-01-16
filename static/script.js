document.addEventListener('DOMContentLoaded', function () {
    const button = document.getElementById('move-up-button');
    const gridContainer = document.querySelector('.grid-container');
    let moved = false;

    button.addEventListener('click', function () {
        if (!moved) {
            gridContainer.classList.add('move-up');  
            moved = true;
        }
    });

    
});

document.addEventListener('DOMContentLoaded', () => {
    const button = document.getElementById('move-up-button');
    let currentBox = null; 
    button.addEventListener('click', () => {
        const inputField = document.querySelector('.input-box');
        const symbol = inputField.value.trim(); 

        if (!symbol) {
            return; 
        }

     
        if (currentBox) {
            currentBox.classList.remove('visible');
            setTimeout(() => {
                currentBox.remove();
                sendDataToFlask(symbol); 
            }, 800);
        } else {
            sendDataToFlask(symbol);
        }
    });

    async function sendDataToFlask(userInput) {
        try {
          
            const spinner = document.getElementById('loading-spinner');
            spinner.style.display = 'block';
    
           
            const response = await fetch('/process', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ user_input: userInput })
            });
    
            
            spinner.style.display = 'none';
    
          
            const result = await response.json();
    
          
            const storedJson = result;
    
            createNewBox(storedJson);
        } catch (error) {
            console.error('Error:', error);
            document.getElementById('output').textContent = 'Error: ' + error;
            const spinner = document.getElementById('loading-spinner');
            spinner.style.display = 'none'; 
        }
    }
    
    
    function createNewBox(data) {
   
        const box = document.createElement('div');
        box.classList.add('fading-box');
    
     
        let content = `<div class="content-wrapper">`;
        for (const key in data) {
            if (data.hasOwnProperty(key)) {
                content += `
                    <div class="content-item">
                        <h4 class="typed-title" data-content="${key}:"></h4>
                        <p class="typed-text" data-content="${data[key]}"></p>
                    </div>
                `;
            }
        }
        content += `</div>`;
    
   
        box.innerHTML = content;
    
    
        const main = document.querySelector('main');
        if (main) {
            main.appendChild(box);
        }
    
     
        setTimeout(() => {
            box.classList.add('visible');
        }, 10);
    
      
        currentBox = box;
    
      
        setTimeout(() => {
            startTypingAnimation();
        }, 3000); 
    }
    
    async function startTypingAnimation() {
        const contentItems = document.querySelectorAll('.content-item');
        
        for (const item of contentItems) {
            const titleElement = item.querySelector('.typed-title');
            const textElement = item.querySelector('.typed-text');
    
            await typeElement(titleElement, 10);  
            await typeElement(textElement, 10); 
        }
    }
    
    function typeElement(element, speed) { 
        return new Promise((resolve) => {
            const fullText = element.getAttribute('data-content');
            element.textContent = '';
            let index = 0;
    
      
            element.classList.add('show-cursor');
    
            function typeCharacter() {
                if (index < fullText.length) {
                    element.textContent += fullText.charAt(index);
                    index++;
                    setTimeout(typeCharacter, speed);  
                } else {
            
                    element.classList.remove('show-cursor');
                    resolve();  
                }
            }
            typeCharacter();
        });
    }
    
});
