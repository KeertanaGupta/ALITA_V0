import axios from 'axios';

const DJANGO_API_URL = 'http://localhost:8000/api/v1/workspace';
const FASTAPI_URL = 'http://localhost:8001/api/v1';

export const djangoClient = axios.create({
  baseURL: DJANGO_API_URL,
});

// --- DJANGO API FUNCTIONS ---
export const fetchProjects = async () => (await djangoClient.get('/projects/')).data;

export const createProject = async (name, description = '') => {
  return (await djangoClient.post('/projects/', { name, description }, { headers: { 'Content-Type': 'application/json' } })).data;
};

export const deleteProject = async (projectId) => (await djangoClient.delete(`/projects/${projectId}/`)).data;

export const updateProject = async (projectId, data) => {
  return (await djangoClient.patch(`/projects/${projectId}/`, data, { headers: { 'Content-Type': 'application/json' } })).data;
};

// CRITICAL FIX: Use pure Axios for files, completely bypassing global JSON headers
export const uploadDocument = async (projectId, file) => {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('project', projectId);
  
  const res = await axios.post(`${DJANGO_API_URL}/documents/`, formData);
  return res.data;
};

export const fetchDocuments = async () => (await djangoClient.get('/documents/')).data;
export const deleteDocument = async (docId) => (await djangoClient.delete(`/documents/${docId}/`)).data;

// CRITICAL FIX: Explicitly send JSON header so Django accepts the status update
export const updateDocumentStatus = async (docId, status) => {
  const res = await djangoClient.patch(`/documents/${docId}/`, 
    { processing_status: status }, 
    { headers: { 'Content-Type': 'application/json' } }
  );
  return res.data;
};

// --- FASTAPI (AI ENGINE) FUNCTIONS ---
export const processDocumentFastAPI = async (documentId, projectId, filePath) => {
  const res = await axios.post(`${FASTAPI_URL}/process-document`, { 
    document_id: documentId, project_id: projectId, file_path: filePath 
  });
  return res.data;
};

export const askAlita = async (question, projectId = 'all') => {
  const res = await axios.post(`${FASTAPI_URL}/chat`, { question, project_id: projectId });
  return res.data;
};

export const fetchSystemStats = async () => (await axios.get(`${FASTAPI_URL}/stats`)).data;
export const switchActiveModel = async (modelName) => (await axios.post(`${FASTAPI_URL}/models/switch`, { model_name: modelName })).data;