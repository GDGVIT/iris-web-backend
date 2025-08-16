// Use current domain for API calls (works for both localhost and deployed domains)
const API_BASE = window.location.origin;
let currentTaskId = null;
let pollingInterval = null;
let graph = null;

class PathFinderUI {
    constructor() {
        this.initializeGraph();
        this.setupEventListeners();
    }

    initializeGraph() {
        const svg = d3.select('#graph');
        
        svg.selectAll('*').remove();
        
        this.tooltip = d3.select('body').append('div')
            .attr('class', 'tooltip');

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
    }

    showLoading() {
        document.getElementById('findPathBtn').disabled = true;
        document.getElementById('error').classList.add('hidden');
    }

    hideLoading() {
        document.getElementById('findPathBtn').disabled = false;
    }

    showError(message) {
        this.hideLoading();
        document.getElementById('error').classList.remove('hidden');
        document.getElementById('errorMessage').textContent = message;
    }

    showVisualizationSection() {
        const section = document.getElementById('visualizationSection');
        section.classList.add('show');
        this.showGraphLoader();
    }

    showGraphLoader() {
        document.getElementById('graphLoader').classList.remove('hidden');
        document.getElementById('graph').classList.add('hidden');
    }

    showGraphVisualization() {
        document.getElementById('graphLoader').classList.add('hidden');
        document.getElementById('graph').classList.remove('hidden');
        
        // Small delay to ensure SVG is rendered
        setTimeout(() => {
            if (graph.simulation) {
                graph.simulation.alpha(0.3).restart();
            }
        }, 100);
    }

    async findPath() {
        const startPage = document.getElementById('startPage').value.trim();
        const endPage = document.getElementById('endPage').value.trim();

        if (!startPage || !endPage) {
            this.showError('Please enter both start and end pages');
            return;
        }

        try {
            this.showLoading();
            this.showVisualizationSection();
            
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
                case 'IN_PROGRESS':
                    setTimeout(() => this.pollTaskStatus(), 1000);
                    break;
                    
                case 'SUCCESS':
                    this.handlePathFound(data.result);
                    break;
                    
                case 'FAILURE':
                    this.hideLoading();
                    const section = document.getElementById('visualizationSection');
                    section.classList.remove('show');
                    this.showError(data.error || 'Task failed');
                    break;
                    
                default:
                    this.showError(`Unknown task status: ${data.status}`);
            }

        } catch (error) {
            this.hideLoading();
            const section = document.getElementById('visualizationSection');
            section.classList.remove('show');
            this.showError(`Failed to check task status: ${error.message}`);
        }
    }

    handlePathFound(result) {
        this.hideLoading();
        
        if (!result.path || result.path.length === 0) {
            // Hide the visualization section and show error
            const section = document.getElementById('visualizationSection');
            section.classList.remove('show');
            this.showError('No path found between the pages');
            return;
        }

        this.showGraphVisualization();
        this.visualizePath(result.path);
        this.displayPathList(result.path, result);
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
        const width = containerRect.width - 48; // Account for padding
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
            .on('mouseover', (event, d) => {
                this.tooltip
                    .style('opacity', 1)
                    .html(`${d.name}<br/>Step ${d.index + 1}`)
                    .style('left', (event.pageX + 10) + 'px')
                    .style('top', (event.pageY - 10) + 'px');
            })
            .on('mouseout', () => {
                this.tooltip.style('opacity', 0);
            })
            .on('click', (event, d) => {
                window.open(`https://en.wikipedia.org/wiki/${encodeURIComponent(d.name)}`, '_blank');
            })
            .on('dblclick', (event, d) => {
                // Double-click to release node from fixed position
                d.fx = null;
                d.fy = null;
                simulation.alphaTarget(0.1).restart();
            })
            .call(d3.drag()
                .on('start', (event, d) => {
                    if (!event.active) simulation.alphaTarget(0.05).restart();
                    d.fx = d.x;
                    d.fy = d.y;
                })
                .on('drag', (event, d) => {
                    const padding = 30;
                    // Constrain drag within bounds
                    d.fx = Math.max(padding, Math.min(width - padding, event.x));
                    d.fy = Math.max(padding, Math.min(calculatedHeight - padding, event.y));
                    // Gentle update without forcing aggressive movement
                })
                .on('end', (event, d) => {
                    if (!event.active) simulation.alphaTarget(0);
                    // Release node to let physics take over for tight binding
                    d.fx = null;
                    d.fy = null;
                    // Gentle restart to pull nodes back together
                    simulation.alphaTarget(0.03).restart();
                    setTimeout(() => simulation.alphaTarget(0), 300);
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
        
        // Very tight physics simulation with text-aware spacing
        const simulation = d3.forceSimulation(nodes)
            .force('link', d3.forceLink(links).id(d => d.id)
                .distance(dynamicDistance)
                .strength(2.0))
            .force('charge', d3.forceManyBody()
                .strength(-200)
                .distanceMax(150))
            .force('center', d3.forceCenter(width / 2, calculatedHeight / 2))
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
                d.x = Math.max(padding, Math.min(width - padding, d.x));
                d.y = Math.max(padding, Math.min(calculatedHeight - padding, d.y));
                // Update truncated text based on current spacing
                d.displayText = getTruncatedText(d.name, dynamicDistance);
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
            labelBg.each(function(d) {
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
        
        // Update stats
        document.getElementById('pathLength').textContent = `${path.length} steps`;
        document.getElementById('searchTime').textContent = `${result.search_time?.toFixed(2) || 'N/A'}s`;
        
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
        if (pollingInterval) {
            clearInterval(pollingInterval);
            pollingInterval = null;
        }
        
        currentTaskId = null;
        
        document.getElementById('error').classList.add('hidden');
        document.getElementById('pathStepsContainer').classList.add('hidden');
        document.getElementById('findPathBtn').disabled = false;
        
        // Hide visualization section
        const section = document.getElementById('visualizationSection');
        section.classList.remove('show');
        this.showGraphLoader();
        
        document.getElementById('startPage').value = '';
        document.getElementById('endPage').value = '';
        
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

window.addEventListener('resize', () => {
    if (pathFinderUI) {
        pathFinderUI.initializeGraph();
    }
});