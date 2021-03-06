import { QueryClient } from 'react-query';
import Axios from 'axios';
// import { stringify } from 'query-string';

if (process.env.REACT_APP_LOCAL) {
  Axios.defaults.baseURL = 'http://localhost:8888';
} else {
  Axios.defaults.baseURL = '/api';
}

// Axios.defaults.paramsSerializer = params => stringify(params);

export const queryClient = new QueryClient();
