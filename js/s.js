export function initializeSpecialResearchApp() {
    let allResearches = [];
    const container = document.getElementById('special-research-container');
    const searchInput = document.getElementById('special-search-input');
    const includeAllCheckbox = document.getElementById('search-include-all');

    // �i�u��1�GDebounce �禡�j
    // �ت��G����禡�Q�L���W�c�a�I�s�C���|�T�O�b�ϥΪ̰����J�@�q�ɶ���A�~����u�����j�M�禡�C
    function debounce(func, delay) {
        let timeout;
        return function(...args) {
            clearTimeout(timeout);
            timeout = setTimeout(() => func.apply(this, args), delay);
        };
    }

    // �u�����j�M�P�L�o�޿�
    function filterAndRender() {
        const searchTerm = searchInput.value.toLowerCase().trim();
        const searchInside = includeAllCheckbox.checked;
        let hasResults = false;

        // �i�u��2�G���A���s�ͦ�HTML�A�ӬO�������/���áj
        // �ڭ̹M���Ҧ��w�s�b���d������
        const allCards = container.querySelectorAll('.research-card');

        allCards.forEach(card => {
            const research = allResearches[card.dataset.index]; // �q�d���W�w�s�����ި��o��l���
            let isMatch = false;

            if (!searchTerm) {
                isMatch = true; // �p�G�j�M�جO�Ū��A��ܩҦ�����
            } else {
                const lowerCaseTitle = research.title.toLowerCase();
                if (lowerCaseTitle.includes(searchTerm)) {
                    isMatch = true;
                } else if (searchInside) {
                    // �`�J�j�M���޿�O������
                    isMatch = research.steps.some(step => {
                        const taskMatch = step.tasks.some(task =>
                            task.description.toLowerCase().includes(searchTerm) ||
                            (task.reward.text && task.reward.text.toLowerCase().includes(searchTerm))
                        );
                        if (taskMatch) return true;

                        if (step.total_rewards) {
                            return step.total_rewards.some(reward =>
                                reward.text && reward.text.toLowerCase().includes(searchTerm)
                            );
                        }
                        return false;
                    });
                }
            }
            
            // �ھڬO�_�ǰt�A�����d������ܪ��A
            if (isMatch) {
                card.style.display = 'block';
                hasResults = true;
            } else {
                card.style.display = 'none';
            }
        });

        // �B�z�u�䤣�쵲�G�v������
        const noResultsMessage = container.querySelector('.no-results');
        if (noResultsMessage) {
            noResultsMessage.style.display = hasResults ? 'none' : 'block';
        }
    }

    fetch('data/special_research.json')
        .then(response => {
            if (!response.ok) {
                throw new Error('�L�k���J JSON �ɮסA�нT�{�ɮצW�٩M���|�O�_���T�C');
            }
            return response.json();
        })
        .then(data => {
            allResearches = data.sort((a, b) => new Date(b.release_date) - new Date(a.release_date));
            
            // �i�u��3�G�������J�ɡA�@���ʥͦ��Ҧ��d���j
            // ���N�Ҧ��d����V��e���W�A������u�|����̪���ܩ�����
            generateResearchCards(allResearches);

            // �� checkbox ���A���ܮɡA�]�ϥ� debounce ��Ĳ�o�j�M�A�קK�s���I���y���d�y
            includeAllCheckbox.addEventListener('change', debounce(filterAndRender, 200));

            // �N 'input' �ƥ󪺺�ť���A�� debounce �]�_�ӡA���� 300 �@�����
            searchInput.addEventListener('input', debounce(filterAndRender, 300));
            
            // �������J��A��ܩҦ����
            filterAndRender();
        })
        .catch(error => {
            container.innerHTML = `<div class="no-results" style="color:red;">${error.message}</div>`;
            console.error('Ū����Ʈɵo�Ϳ��~:', error);
        });

    // ������ �z�쥻���Ҧ� helper functions (generateResearchCards, generateListHtml, addAccordionLogic) �]�n�@�ֽƻs��o�� ������
    // �i���n�ק�jgenerateResearchCards �{�b�u�b��l�ɳQ�I�s�@��
    function generateResearchCards(researches) {
        container.innerHTML = ''; // �M�Ůe���A�ǳƥͦ�

        if (researches.length === 0) {
            container.innerHTML = '<div class="no-results">�䤣��ŦX���󪺽լd ? <br>�ոլݧO������r�a�I</div>';
            return;
        }

        const fragment = document.createDocumentFragment(); // �ϥΤ��ɸH�������į�

        researches.forEach((research, index) => {
            const card = document.createElement('div');
            card.className = 'research-card';
            card.dataset.index = index; // �i����j�N��l��ƪ����ަs�_�ӡA��K����^��

            const stepsHtml = research.steps.map(step => {
                const tasksHtml = generateListHtml(step.tasks, 'task');
                const totalRewardsHtml = step.total_rewards && step.total_rewards.length > 0
                    ? `<div class="total-rewards-container">
                           <h4>? �������q�`���y</h4>
                           <ul class="total-rewards-grid">${generateListHtml(step.total_rewards, 'total')}</ul>
                       </div>`
                    : '';

                return `
                    <div class="step">
                        <h3>${step.step_title}</h3>
                        <ul>${tasksHtml}</ul>
                        ${totalRewardsHtml}
                    </div>
                `;
            }).join('');

            card.innerHTML = `
                <div class="research-title">
                    <div class="research-title-block">
                        <span class="research-title-text">${research.title}</span>
                        <span class="research-date">�o�����: ${research.release_date || 'N/A'}</span>
                    </div>
                    <span class="icon">+</span>
                </div>
                <div class="research-content">
                    ${stepsHtml}
                </div>
            `;
            
            fragment.appendChild(card);
        });

        // �[�W�@�өT�w���u�L���G�v���ܤ����A�����JS��������/����
        const noResultsDiv = document.createElement('div');
        noResultsDiv.className = 'no-results';
        noResultsDiv.textContent = '�䤣��ŦX���󪺽լd ? �ոլݧO������r�a�I';
        noResultsDiv.style.display = 'none'; // �w�]����
        fragment.appendChild(noResultsDiv);
        
        container.appendChild(fragment); // �@���ʱN�Ҧ������[�JDOM
        
        addAccordionLogic(); // �⭷�^�ĪG����ť���]�u�ݭn�]�w�@��
    }

    // generateListHtml �禡��������
    function generateListHtml(items, type) {
        // ... ���禡���e�������ܡA�ЫO�d�z�쥻���{���X ...
        const placeholderSrc = "data:image/gif;base64,R0lGODlhAQABAAD/ACwAAAAAAQABAAACADs=";

        return items.map(item => {
            let description, rewardText, imageUrls;

            if (type === 'task') {
                description = item.description;
                rewardText = item.reward.text;
                imageUrls = item.reward.image_urls || [];
                const imagesHtml = imageUrls.map(url => `<img src="${placeholderSrc}" data-src="${url}" alt="reward" class="reward-icon lazy-load">`).join('');
                const rewardTextHtml = rewardText ? `<span>(${rewardText})</span>` : '';

                return `
                    <li class="task-item">
                        <span class="task-description">${description}</span>
                        <div class="task-reward">
                            ${rewardTextHtml}
                            ${imagesHtml}
                        </div>
                    </li>`;

            } else { 
                description = item.text;
                imageUrls = item.image_url ? [item.image_url] : [];
                const imagesHtml = imageUrls.map(url => `<img src="${placeholderSrc}" data-src="${url}" alt="reward" class="reward-icon lazy-load">`).join('');

                return `
                    <li class="total-reward-item">
                        ${imagesHtml}
                        <span class="total-reward-text">${description}</span>
                    </li>`;
            }
        }).join('');
    }

    // addAccordionLogic �禡��������
    function addAccordionLogic() {
        // ... ���禡���e�������ܡA�ЫO�d�z�쥻���{���X ...
        const titles = document.querySelectorAll('.research-title');

        titles.forEach(title => {
            title.addEventListener('click', () => {
                const isActive = title.classList.contains('active');
                title.classList.toggle('active', !isActive);
                const content = title.nextElementSibling;

                if (!isActive) {
                    content.classList.add('show');
                    content.style.maxHeight = content.scrollHeight + 50 + "px";

                    const imagesToLoad = content.querySelectorAll('img.lazy-load');
                    imagesToLoad.forEach(img => {
                        img.src = img.dataset.src;
                        img.classList.remove('lazy-load');
                        img.onload = () => {
                            img.style.opacity = '1';
                        };
                    });

                } else {
                    content.style.maxHeight = null;
                    content.classList.remove('show');
                }
            });
        });
    }
}