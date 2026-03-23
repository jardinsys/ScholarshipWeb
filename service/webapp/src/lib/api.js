import axios from 'axios'

const api = axios.create({
  baseURL: '/api',          // proxied to http://localhost:3000 via vite.config.js
  timeout: 10_000,
  headers: { 'Content-Type': 'application/json' },
})

// Users
export const getUser       = (id)       => api.get(`/users/${id}`)
export const updateUser    = (id, data) => api.put(`/users/${id}`, data)
export const getUserTags   = (id)       => api.get(`/users/${id}/tags`)
export const addUserTag    = (id, tag)  => api.post(`/users/${id}/tags`, tag)
export const removeUserTag = (id, tagId)=> api.delete(`/users/${id}/tags/${tagId}`)
export const register = (username) => api.post('/users/register', { username })
export const login    = (username) => api.post('/users/login',    { username })

// Tags (global catalogue)
export const getAllTags  = ()      => api.get('/tags')
export const createTag  = (data)  => api.post('/tags', data)

// Scholarships
export const getScholarships       = (params) => api.get('/scholarships', { params })
export const getMatchedScholarships = (userId) => api.get(`/users/${userId}/matches`)
export const saveScholarship   = (userId, scholarshipId) => api.post(`/users/${userId}/saved/${scholarshipId}`)
export const unsaveScholarship = (userId, scholarshipId) => api.delete(`/users/${userId}/saved/${scholarshipId}`)
export const getSaved          = (userId)                => api.get(`/users/${userId}/saved`)

export default api