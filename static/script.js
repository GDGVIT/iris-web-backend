// Use current domain for API calls (works for both localhost and deployed domains)
const API_BASE = window.location.origin;
let currentTaskId = null;
let pollingInterval = null;
let graph = null;

// State management
const StateManager = {
    save(data) {
        localStorage.setItem('iris_state', JSON.stringify(data));
    },

    load() {
        const stored = localStorage.getItem('iris_state');
        return stored ? JSON.parse(stored) : null;
    },

    clear() {
        localStorage.removeItem('iris_state');
    }
};

class PathFinderUI {
    constructor() {
        this.initializeGraph();
        this.setupEventListeners();
        this.restoreStateFromStorage();
    }

    initializeGraph() {
        const svg = d3.select('#graph');

        svg.selectAll('*').remove();

        // Reuse existing tooltip if present to avoid duplicates
        this.tooltip = d3.select('.tooltip');
        if (this.tooltip.empty()) {
            this.tooltip = d3.select('body').append('div')
                .attr('class', 'tooltip');
        }

        graph = {
            svg: svg,
            width: 0, // Will be set in renderGraph
            height: 500,
            nodes: [],
            links: [],
            simulation: null
        };
    }

    setupEventListeners() {
        document.getElementById('startPage').addEventListener('keypress', (e) => {
            if (e.key === 'Enter') this.findPath();
        });

        document.getElementById('endPage').addEventListener('keypress', (e) => {
            if (e.key === 'Enter') this.findPath();
        });

        // Auto-save state and update button state on input changes
        document.getElementById('startPage').addEventListener('input', () => {
            this.saveCurrentState();
            this.updateButtonState();
        });
        document.getElementById('endPage').addEventListener('input', () => {
            this.saveCurrentState();
            this.updateButtonState();
        });
    }

    restoreStateFromStorage() {
        const savedState = StateManager.load();
        if (savedState) {
            if (savedState.startPage) {
                document.getElementById('startPage').value = savedState.startPage;
            }
            if (savedState.endPage) {
                document.getElementById('endPage').value = savedState.endPage;
            }

            // If there's an active task, try to restore it
            if (savedState.taskId && savedState.status === 'IN_PROGRESS') {
                currentTaskId = savedState.taskId;
                this.showVisualizationSection();
                this.showProgressLoader();
                // Ensure header matches saved pages and stats are reset until updates arrive
                this.resetProgressUI();
                this.showLoading(); // Disable button for active task
                this.pollTaskStatus();
            } else if (savedState.result && savedState.result.path) {
                // Restore completed result
                this.showVisualizationSection();
                this.handlePathFound(savedState.result);
            }
        }
        
        // Update button state after restoration
        this.updateButtonState();
    }

    saveCurrentState() {
        const state = {
            startPage: document.getElementById('startPage').value,
            endPage: document.getElementById('endPage').value,
            taskId: currentTaskId,
            status: currentTaskId ? 'IN_PROGRESS' : 'IDLE',
            timestamp: Date.now()
        };
        StateManager.save(state);
    }

    updateButtonState() {
        const startPage = document.getElementById('startPage').value.trim();
        const endPage = document.getElementById('endPage').value.trim();
        const savedState = StateManager.load();
        
        // Button should be disabled if:
        // 1. Currently loading (currentTaskId exists)
        // 2. Input fields are empty
        // 3. Current inputs match saved completed result (no change)
        
        let shouldDisable = false;
        
        // Check if currently loading
        if (currentTaskId) {
            shouldDisable = true;
        }
        // Check if inputs are empty
        else if (!startPage || !endPage) {
            shouldDisable = true;
        }
        // Check if current inputs match saved completed result
        else if (savedState && savedState.status === 'COMPLETED' && savedState.result) {
            const matchesSaved = (
                startPage === savedState.startPage && 
                endPage === savedState.endPage
            );
            if (matchesSaved) {
                shouldDisable = true;
            }
        }
        
        document.getElementById('findPathBtn').disabled = shouldDisable;
    }

    clearActiveTask() {
        // Stop any ongoing polling
        if (pollingInterval) {
            clearInterval(pollingInterval);
            pollingInterval = null;
        }
        
        // Clear current task ID
        currentTaskId = null;
        
        // Update button state
        this.updateButtonState();
    }

    showLoading() {
        document.getElementById('findPathBtn').disabled = true;
        document.getElementById('error').classList.add('hidden');
    }

    hideLoading() {
        // Use updateButtonState instead of directly enabling
        this.updateButtonState();
    }

    showError(message) {
        this.hideLoading();
        document.getElementById('error').classList.remove('hidden');
        document.getElementById('errorMessage').textContent = message;
    }

    showVisualizationSection() {
        const section = document.getElementById('visualizationSection');
        section.classList.add('show');
        // Show the unified progress loader immediately to avoid flicker
        this.showProgressLoader();
        // Reset UI to a clean slate for this run
        this.resetProgressUI();
    }

    showGraphLoader() {
        const container = document.getElementById('graphContainer');
        container.classList.add('loading');
        document.getElementById('graphLoader').classList.remove('hidden');
        document.getElementById('searchProgress').classList.add('hidden');
        document.getElementById('graph').classList.add('hidden');
    }

    showProgressLoader() {
        const container = document.getElementById('graphContainer');
        container.classList.add('loading');
        document.getElementById('graphLoader').classList.add('hidden');
        const sp = document.getElementById('searchProgress');
        sp.classList.remove('hidden');
        document.getElementById('graph').classList.add('hidden');
    }

    resetProgressUI() {
        // Ensure header matches current inputs
        const startPage = document.getElementById('startPage').value.trim() || '-';
        const endPage = document.getElementById('endPage').value.trim() || '-';
        document.getElementById('searchPath').textContent = `${startPage} → ${endPage}`;

        // Zero stats
        document.getElementById('nodesExplored').textContent = '0';
        document.getElementById('queueSize').textContent = '0';
        document.getElementById('elapsedTime').textContent = '0s';

        // Disable last node click
        const lastNodeEl = document.getElementById('lastNode');
        lastNodeEl.textContent = '-';
        lastNodeEl.classList.add('disabled');

        // Reset depth
        this.updateDepthIndicator(0, 6);
    }

    updateProgressDisplay(progressData) {
        if (!progressData || !progressData.search_stats) {
            return;
        }

        const stats = progressData.search_stats;
        
        // Update search path header
        document.getElementById('searchPath').textContent = 
            `${stats.start_page} → ${stats.end_page}`;
        
        // Update depth indicator
        this.updateDepthIndicator(stats.current_depth, stats.max_depth || 6);
        
        // Update statistics
        document.getElementById('nodesExplored').textContent = 
            stats.nodes_explored?.toLocaleString() || '0';
        document.getElementById('queueSize').textContent = 
            stats.queue_size?.toLocaleString() || '0';
        document.getElementById('elapsedTime').textContent = 
            `${progressData.search_time_elapsed || 0}s`;
        const lastNodeEl = document.getElementById('lastNode');
        const ln = stats.last_node || '-';
        lastNodeEl.textContent = ln;
        if (ln && ln !== '-') {
            lastNodeEl.classList.remove('disabled');
        } else {
            lastNodeEl.classList.add('disabled');
        }
    }

    updateDepthIndicator(currentDepth, maxDepth) {
        const dots = document.querySelectorAll('#depthDots .depth-dot');
        
        dots.forEach((dot, index) => {
            dot.classList.remove('active', 'completed');
            
            if (index < currentDepth) {
                dot.classList.add('completed');
            } else if (index === currentDepth) {
                dot.classList.add('active');
            }
        });
    }

    showGraphVisualization() {
        const container = document.getElementById('graphContainer');
        container.classList.remove('loading');
        document.getElementById('graphLoader').classList.add('hidden');
        document.getElementById('searchProgress').classList.add('hidden');
        document.getElementById('graph').classList.remove('hidden');

        // Small delay to ensure SVG is rendered
        setTimeout(() => {
            if (graph.simulation) {
                graph.simulation.alpha(0.3).restart();
            }
        }, 100);
    }

    hidePathDisplay() {
        // Hide the path steps container and progress display
        document.getElementById('pathStepsContainer').classList.add('hidden');
        document.getElementById('searchProgress').classList.add('hidden');
        
        // Clear the graph visualization
        if (graph && graph.svg) {
            graph.svg.selectAll('*').remove();
        }
        // Return container to loading state while hidden
        const container = document.getElementById('graphContainer');
        container.classList.add('loading');
    }

    async findPath() {
        const startPage = document.getElementById('startPage').value.trim();
        const endPage = document.getElementById('endPage').value.trim();

        if (!startPage || !endPage) {
            this.showError('Please enter both start and end pages');
            return;
        }

        // If there's already a running task, this new request will replace it
        if (currentTaskId) {
            // Clear the previous task state
            this.clearActiveTask();
        }

        try {
            this.showLoading();
            this.hidePathDisplay();
            this.showVisualizationSection();
            
            // Update search path header immediately with actual pages
            document.getElementById('searchPath').textContent = `${startPage} → ${endPage}`;

            const response = await fetch(`${API_BASE}/getPath`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    start: startPage,
                    end: endPage
                })
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.message || `HTTP ${response.status}`);
            }

            const data = await response.json();
            currentTaskId = data.task_id;

            // Save task ID to state for recovery
            this.saveCurrentState();

            this.pollTaskStatus();

        } catch (error) {
            const section = document.getElementById('visualizationSection');
            section.classList.remove('show');
            this.showError(`Failed to start pathfinding: ${error.message}`);
        }
    }

    async pollTaskStatus() {
        if (!currentTaskId) return;

        try {
            const response = await fetch(`${API_BASE}/tasks/status/${currentTaskId}`);

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }

            const data = await response.json();

            switch (data.status) {
                case 'PENDING':
                    // Keep the progress loader visible while waiting for first callback
                    this.showProgressLoader();
                    // Show zeroed stats while we wait
                    this.resetProgressUI();
                    // Header already shows start→end; stats will populate on first update
                    setTimeout(() => this.pollTaskStatus(), 1000);
                    break;

                case 'IN_PROGRESS':
                    // Switch to progress display and update with real data
                    this.showProgressLoader();
                    if (data.progress) {
                        this.updateProgressDisplay(data.progress);
                    }
                    setTimeout(() => this.pollTaskStatus(), 1000);
                    break;

                case 'SUCCESS':
                    this.handlePathFound(data.result);
                    break;

                case 'FAILURE':
                    this.clearActiveTask();
                    this.hideLoading();
                    const section = document.getElementById('visualizationSection');
                    section.classList.remove('show');
                    this.showError(data.error || 'Task failed');
                    StateManager.clear();
                    break;

                default:
                    this.clearActiveTask();
                    this.showError(`Unknown task status: ${data.status}`);
                    StateManager.clear();
            }

        } catch (error) {
            this.clearActiveTask();
            this.hideLoading();
            const section = document.getElementById('visualizationSection');
            section.classList.remove('show');
            this.showError(`Failed to check task status: ${error.message}`);
            StateManager.clear();
        }
    }

    handlePathFound(result) {
        this.hideLoading();

        if (!result.path || result.path.length === 0) {
            // Hide the visualization section and show error
            const section = document.getElementById('visualizationSection');
            section.classList.remove('show');
            this.showError('No path found between the pages');
            StateManager.clear();
            return;
        }

        // Save successful result to state
        const state = StateManager.load() || {};
        state.result = result;
        state.status = 'COMPLETED';
        StateManager.save(state);

        this.showGraphVisualization();
        this.visualizePath(result.path);
        this.displayPathList(result.path, result);

        // Clear task ID since it's completed and update button state
        currentTaskId = null;
        this.updateButtonState();
    }

    // Re-render graph responsively based on saved, completed result
    rerenderFromState() {
        const savedState = StateManager.load();
        if (savedState && savedState.status === 'COMPLETED' && savedState.result && savedState.result.path) {
            this.initializeGraph();
            this.visualizePath(savedState.result.path);
            this.showGraphVisualization();
        }
    }

    visualizePath(path) {
        const nodes = path.map((page, index) => ({
            id: page,
            name: page,
            index: index,
            isStart: index === 0,
            isEnd: index === path.length - 1,
            textWidth: page.length * 8 + 20 // Estimate text width for collision detection
        }));

        const links = [];
        for (let i = 0; i < path.length - 1; i++) {
            links.push({
                source: path[i],
                target: path[i + 1],
                isPath: true
            });
        }

        this.renderGraph(nodes, links);
    }

    renderGraph(nodes, links) {
        const { svg } = graph;

        svg.selectAll('*').remove();

        // Get actual container dimensions
        const container = document.getElementById('graphContainer');
        const containerRect = container.getBoundingClientRect();
        const width = containerRect.width - 64; // Account for 32px left + 32px right padding
        const nodeCount = nodes.length;
        const calculatedHeight = Math.max(400, Math.min(600, nodeCount * 60));

        // Update graph object
        graph.width = width;
        graph.height = calculatedHeight;

        // Set SVG dimensions properly  
        svg
            .attr('width', width)
            .attr('height', calculatedHeight)
            .attr('viewBox', `0 0 ${width} ${calculatedHeight}`)
            .style('display', 'block');

        // Add arrow marker for directed edges
        const defs = svg.append('defs');
        defs.append('marker')
            .attr('id', 'arrowhead')
            .attr('viewBox', '0 -5 10 10')
            .attr('refX', 5)
            .attr('refY', 0)
            .attr('markerWidth', 6)
            .attr('markerHeight', 6)
            .attr('orient', 'auto')
            .append('path')
            .attr('d', 'M0,-5L10,0L0,5')
            .attr('fill', '#58A6FF');

        // Create main group
        const g = svg.append('g');

        // Create links as paths for better arrow control
        const link = g.append('g')
            .attr('class', 'links')
            .selectAll('path')
            .data(links)
            .enter().append('path')
            .attr('class', d => d.isPath ? 'link path' : 'link')
            .attr('marker-mid', 'url(#arrowhead)');

        // Create nodes
        let isDragging = false;
        const node = g.append('g')
            .attr('class', 'nodes')
            .selectAll('circle')
            .data(nodes)
            .enter().append('circle')
            .attr('class', d => {
                let classes = 'node';
                if (d.isStart) classes += ' start';
                if (d.isEnd) classes += ' end';
                return classes;
            })
            .attr('r', 14)
            // Ensure touch devices dedicate gestures to drag
            .style('touch-action', 'none')
            .on('mouseover', (event, d) => {
                // Avoid tooltip on touch to prevent interference
                const isTouch = event?.pointerType === 'touch' || event?.type?.startsWith('touch');
                if (isTouch) return;
                this.tooltip
                    .style('opacity', 1)
                    .html(`${d.name}<br/>Step ${d.index + 1}`)
                    .style('left', (event.pageX + 10) + 'px')
                    .style('top', (event.pageY - 10) + 'px');
            })
            .on('mouseout', (event) => {
                const isTouch = event?.pointerType === 'touch' || event?.type?.startsWith('touch');
                if (isTouch) return;
                this.tooltip.style('opacity', 0);
            })
            .on('click', (event, d) => {
                if (isDragging) return;
                window.open(`https://en.wikipedia.org/wiki/${encodeURIComponent(d.name)}`, '_blank');
            })
            .on('dblclick', (event, d) => {
                // Double-click to release node from fixed position
                d.fx = null;
                d.fy = null;
                simulation.alphaTarget(0.08).restart();
                setTimeout(() => simulation.alphaTarget(0), 150);
            })
            .call(d3.drag()
                .on('start', (event, d) => {
                    // Prevent native scrolling/gestures only for touch
                    const se = event.sourceEvent;
                    const isTouch = se && (se.pointerType === 'touch' || se.type === 'touchstart');
                    if (isTouch) {
                        se.preventDefault();
                        se.stopPropagation();
                    }
                    isDragging = true;
                    if (!event.active) simulation.alphaTarget(0.05).restart();
                    d.fx = d.x;
                    d.fy = d.y;
                })
                .on('drag', (event, d) => {
                    const padding = 30;
                    // Prevent default touch behaviors during drag
                    const se = event.sourceEvent;
                    const isTouch = se && (se.pointerType === 'touch' || se.type === 'touchmove');
                    if (isTouch) {
                        se.preventDefault();
                    }
                    // Constrain drag within bounds
                    d.fx = Math.max(padding, Math.min(graph.width - padding, event.x));
                    d.fy = Math.max(padding, Math.min(graph.height - padding, event.y));
                })
                .on('end', (event, d) => {
                    if (!event.active) simulation.alphaTarget(0);
                    // Release node to let physics take over for tight binding
                    d.fx = null;
                    d.fy = null;
                    // Gentle restart to pull nodes back together without jolts
                    simulation.alphaTarget(0.02).restart();
                    setTimeout(() => {
                        simulation.alphaTarget(0);
                        isDragging = false;
                    }, 200);
                }));

        // Create label backgrounds (opaque boxes)
        const labelBg = g.append('g')
            .attr('class', 'label-backgrounds')
            .selectAll('rect')
            .data(nodes)
            .enter().append('rect')
            .attr('class', 'node-label-bg')
            .attr('rx', 4)
            .attr('ry', 4);

        // Create labels
        const label = g.append('g')
            .attr('class', 'labels')
            .selectAll('text')
            .data(nodes)
            .enter().append('text')
            .attr('class', 'node-label')
            .attr('dy', 35);

        // Calculate dynamic link distance based on text lengths
        const maxTextWidth = Math.max(...nodes.map(d => d.textWidth));
        const dynamicDistance = Math.max(80, maxTextWidth + 30);
        graph.dynamicDistance = dynamicDistance;

        // Very tight physics simulation with text-aware spacing
        const simulation = d3.forceSimulation(nodes)
            .force('link', d3.forceLink(links).id(d => d.id)
                .distance(() => graph.dynamicDistance)
                .strength(2.0))
            .force('charge', d3.forceManyBody()
                .strength(-200)
                .distanceMax(150))
            .force('center', d3.forceCenter(graph.width / 2, graph.height / 2))
            .force('collision', d3.forceCollide()
                .radius(d => Math.max(30, d.textWidth / 2 + 10))
                .strength(1.0))
            .alphaDecay(0.01)
            .velocityDecay(0.6);

        // Function to truncate text based on graph density
        function getTruncatedText(name, distance) {
            const maxLength = Math.max(8, Math.floor(distance / 8));
            if (name.length <= maxLength) return name;
            return name.substring(0, maxLength - 3) + '...';
        }

        // Update positions on each tick with proper edge constraints
        simulation.on('tick', () => {
            const padding = 30;

            // Constrain node positions and update coordinates
            nodes.forEach(d => {
                d.x = Math.max(padding, Math.min(graph.width - padding, d.x));
                d.y = Math.max(padding, Math.min(graph.height - padding, d.y));
                // Update truncated text based on current spacing
                d.displayText = getTruncatedText(d.name, graph.dynamicDistance);
            });

            link
                .attr('d', d => {
                    const midX = (d.source.x + d.target.x) / 2;
                    const midY = (d.source.y + d.target.y) / 2;
                    return `M${d.source.x},${d.source.y} L${midX},${midY} L${d.target.x},${d.target.y}`;
                });

            node
                .attr('cx', d => d.x)
                .attr('cy', d => d.y);

            // Update labels with dynamic text
            label
                .attr('x', d => d.x)
                .attr('y', d => d.y)
                .text(d => d.displayText);

            // Update label backgrounds with generous padding
            labelBg.each(function (d) {
                const textLength = d.displayText.length * 7;
                const horizontalPadding = 16;
                const verticalPadding = 6;
                const boxWidth = textLength + (horizontalPadding * 2);
                const boxHeight = 16 + (verticalPadding * 2);
                d3.select(this)
                    .attr('x', d.x - boxWidth / 2)
                    .attr('y', d.y + 35 - (boxHeight / 2) - 4)
                    .attr('width', boxWidth)
                    .attr('height', boxHeight);
            });
        });

        // Start with lower alpha for smoother initial animation
        simulation.alpha(0.5).restart();

        // Let simulation settle naturally
        setTimeout(() => {
            simulation.alphaTarget(0);
        }, 1500);

        graph.simulation = simulation;
    }

    displayPathList(path, result) {
        const pathStepsContainer = document.getElementById('pathStepsContainer');
        const pathSteps = document.getElementById('pathSteps');

        // Update stats - simple badges design
        document.getElementById('pathLength').textContent = `${path.length} steps`;
        document.getElementById('searchTime').textContent = `${result.search_time?.toFixed(2) || 'N/A'}s`;
        
        // Add nodes explored to the badges (singular/plural)
        const nodesExplored = result.search_stats?.nodes_explored || result.nodes_explored || 0;
        const nodeText = nodesExplored === 1 ? 'node' : 'nodes';
        document.getElementById('nodesExploredStat').textContent = `${nodesExplored.toLocaleString()} ${nodeText}`;

        pathSteps.innerHTML = '';

        path.forEach((page, index) => {
            const stepDiv = document.createElement('div');
            stepDiv.className = 'path-step';
            stepDiv.onclick = () => {
                window.open(`https://en.wikipedia.org/wiki/${encodeURIComponent(page)}`, '_blank');
            };

            const stepNumber = document.createElement('div');
            stepNumber.className = 'step-number';
            stepNumber.textContent = index + 1;

            const stepTitle = document.createElement('div');
            stepTitle.className = 'step-title';
            stepTitle.textContent = page;

            stepDiv.appendChild(stepNumber);
            stepDiv.appendChild(stepTitle);
            pathSteps.appendChild(stepDiv);
        });

        pathStepsContainer.classList.remove('hidden');
    }

    clearVisualization() {
        // Clear active task if any
        this.clearActiveTask();

        // Clear stored state
        StateManager.clear();

        document.getElementById('error').classList.add('hidden');
        document.getElementById('pathStepsContainer').classList.add('hidden');

        // Hide visualization section
        const section = document.getElementById('visualizationSection');
        section.classList.remove('show');
        this.showGraphLoader();

        document.getElementById('startPage').value = '';
        document.getElementById('endPage').value = '';

        // Update button state after clearing inputs
        this.updateButtonState();

        if (graph && graph.svg) {
            graph.svg.selectAll('g').remove();
            // Reset any fixed positions
            if (graph.simulation) {
                graph.simulation.nodes().forEach(d => {
                    d.fx = null;
                    d.fy = null;
                });
            }
        }
    }
}

let pathFinderUI;

function findPath() {
    if (pathFinderUI) {
        pathFinderUI.findPath();
    }
}

function clearVisualization() {
    if (pathFinderUI) {
        pathFinderUI.clearVisualization();
    }
}

document.addEventListener('DOMContentLoaded', () => {
    pathFinderUI = new PathFinderUI();
});

// Simple debounce to avoid thrashing on mobile address bar show/hide
function debounce(fn, wait) {
    let t;
    return function (...args) {
        clearTimeout(t);
        t = setTimeout(() => fn.apply(this, args), wait);
    };
}

// Resize without re-rendering: only update svg size and forces
PathFinderUI.prototype.resizeGraph = function () {
    if (!graph || !graph.svg || !graph.simulation) return;

    const container = document.getElementById('graphContainer');
    if (!container) return;
    const { width: containerWidth } = container.getBoundingClientRect();

    const newWidth = containerWidth - 64; // 32px left + 32px right padding
    const nodeCount = graph.simulation.nodes().length || 0;
    const newHeight = Math.max(400, Math.min(600, nodeCount * 60));

    // Update graph dimensions
    graph.width = newWidth;
    graph.height = newHeight;

    // Update svg size without wiping elements
    graph.svg
        .attr('width', graph.width)
        .attr('height', graph.height)
        .attr('viewBox', `0 0 ${graph.width} ${graph.height}`)
        .style('display', 'block');


    // Update forces to reflect new center and spacing
    const nodes = graph.simulation.nodes();
    const maxTextWidth = Math.max(...nodes.map(d => d.textWidth || 0), 0);
    graph.dynamicDistance = Math.max(80, maxTextWidth + 30);

    const linkForce = graph.simulation.force('link');
    if (linkForce && typeof linkForce.distance === 'function') {
        linkForce.distance(() => graph.dynamicDistance);
    }

    graph.simulation
        .force('center', d3.forceCenter(graph.width / 2, graph.height / 2))
        .alphaTarget(0.05)
        .restart();

    // Settle gently
    setTimeout(() => graph.simulation.alphaTarget(0), 300);
};

window.addEventListener('resize', debounce(() => {
    if (!pathFinderUI) return;
    const sectionVisible = document.getElementById('visualizationSection')?.classList.contains('show');
    if (sectionVisible) {
        pathFinderUI.resizeGraph();
    }
}, 120));

// Helper function for opening Wikipedia pages
function openWikipediaPage(pageName) {
    if (pageName && pageName !== '-') {
        window.open(`https://en.wikipedia.org/wiki/${encodeURIComponent(pageName)}`, '_blank');
    }
}
