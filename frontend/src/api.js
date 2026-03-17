import axios from 'axios';

// The base URL for your Django REST API
const DJANGO_API_URL = 'http://localhost:8000/api/v1/workspace';

// Create a configured Axios client
export const djangoClient = axios.create({
  baseURL: DJANGO_API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// --- API FUNCTIONS ---

// 1. Fetch all projects
export const fetchProjects = async () => {
  try {
    const response = await djangoClient.get('/projects/');
    return response.data;
  } catch (error) {
    console.error("Error fetching projects:", error);
    throw error;
  }
};

// 2. Create a new project
export const createProject = async (name, description = '') => {
  try {
    const response = await djangoClient.post('/projects/', { name, description });
    return response.data;
  } catch (error) {
    console.error("Error creating project:", error);
    throw error;
  }
};

// 3. Upload a document to a project
export const uploadDocument = async (projectId, file, onProgressCallback) => {
  const formData = new FormData();
  formData.append('project', projectId);
  formData.append('file', file);

  try {
    const response = await djangoClient.post('/documents/', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
      onUploadProgress: (progressEvent) => {
        const percentCompleted = Math.round((progressEvent.loaded * 100) / progressEvent.total);
        if (onProgressCallback) onProgressCallback(percentCompleted);
      }
    });
    return response.data;
  } catch (error) {
    console.error("Error uploading document:", error);
    throw error;
  }
};

// --- FASTAPI (AI ENGINE) FUNCTIONS ---

// The base URL for your FastAPI AI Engine
const FASTAPI_URL = 'http://localhost:8001/api/v1';

// 4. Ask a question to the Offline RAG pipeline with Project Filtering
export const askAlita = async (question, projectId = 'all') => {
  try {
    const response = await axios.post(`${FASTAPI_URL}/chat`, { 
      question: question,
      project_id: projectId 
    });
    return response.data;
  } catch (error) {
    console.error("Error talking to AI Engine:", error);
    throw error;
  }
};