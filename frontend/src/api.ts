/**
 * Generated by orval v6.7.1 🍺
 * Do not edit manually.
 * mydiary
 * OpenAPI spec version: 0.1.0
 */
import axios,{
  AxiosRequestConfig,
  AxiosResponse,
  AxiosError
} from 'axios'
import {
  useQuery,
  useMutation,
  UseQueryOptions,
  UseMutationOptions,
  QueryFunction,
  MutationFunction,
  UseQueryResult,
  QueryKey
} from 'react-query'
export type ReadSpotifyHistoryParams = { offset?: number; limit?: number };

export type ReadPocketArticlesParams = { offset?: number; limit?: number; status?: number[]; tags?: string[]; year?: number };

export type ReadTagsParams = { offset?: number; limit?: number };

export type ReadGCalEventsParams = { offset?: number; limit?: number };

export interface ValidationError {
  loc: string[];
  msg: string;
  type: string;
}

export interface TagRead {
  id: number;
  name: string;
  is_pocket_tag?: boolean;
}

export interface SpotifyTrackHistoryRead {
  spotify_id: string;
  name: string;
  artist_name: string;
  uri: string;
  played_at: string;
  context_type?: string;
  context_uri?: string;
  id: number;
}

/**
 * An enumeration.
 */
export type PocketStatusEnum = 0 | 1 | 2;


// eslint-disable-next-line @typescript-eslint/no-redeclare
export const PocketStatusEnum = {
  NUMBER_0: 0 as PocketStatusEnum,
  NUMBER_1: 1 as PocketStatusEnum,
  NUMBER_2: 2 as PocketStatusEnum,
};

export interface PocketArticleRead {
  id: number;
  given_title: string;
  resolved_title: string;
  url: string;
  favorite: boolean;
  status: PocketStatusEnum;
  time_added?: string;
  time_updated?: string;
  time_read?: string;
  time_favorited?: string;
  listen_duration_estimate?: number;
  word_count?: number;
  excerpt?: string;
  top_image_url?: string;
  tags: TagRead[];
}

export interface HTTPValidationError {
  detail?: ValidationError[];
}

export interface GooglePhotosThumbnail {
  baseUrl: string;
  width: number;
  height: number;
}

export interface GoogleCalendarEventRead {
  id: string;
  summary: string;
  location?: string;
  description?: string;
  start: string;
  end: string;
  start_timezone: string;
  end_timezone: string;
}



// eslint-disable-next-line @typescript-eslint/no-explicit-any
type AsyncReturnType<
T extends (...args: any) => Promise<any>
> = T extends (...args: any) => Promise<infer R> ? R : any;


/**
 * @summary Read Gcal Events
 */
export const readGCalEvents = (
    params?: ReadGCalEventsParams, options?: AxiosRequestConfig
 ): Promise<AxiosResponse<GoogleCalendarEventRead[]>> => {
    return axios.get(
      `/gcal/events`,{
        params,
    ...options}
    );
  }


export const getReadGCalEventsQueryKey = (params?: ReadGCalEventsParams,) => [`/gcal/events`, ...(params ? [params]: [])];

    
export type ReadGCalEventsQueryResult = NonNullable<AsyncReturnType<typeof readGCalEvents>>
export type ReadGCalEventsQueryError = AxiosError<HTTPValidationError>

export const useReadGCalEvents = <TData = AsyncReturnType<typeof readGCalEvents>, TError = AxiosError<HTTPValidationError>>(
 params?: ReadGCalEventsParams, options?: { query?:UseQueryOptions<AsyncReturnType<typeof readGCalEvents>, TError, TData>, axios?: AxiosRequestConfig}

  ):  UseQueryResult<TData, TError> & { queryKey: QueryKey } => {

  const {query: queryOptions, axios: axiosOptions} = options || {}

  const queryKey = queryOptions?.queryKey ?? getReadGCalEventsQueryKey(params);

  

  const queryFn: QueryFunction<AsyncReturnType<typeof readGCalEvents>> = () => readGCalEvents(params, axiosOptions);

  const query = useQuery<AsyncReturnType<typeof readGCalEvents>, TError, TData>(queryKey, queryFn, queryOptions)

  return {
    queryKey,
    ...query
  }
}


/**
 * @summary Read Tags
 */
export const readTags = (
    params?: ReadTagsParams, options?: AxiosRequestConfig
 ): Promise<AxiosResponse<TagRead[]>> => {
    return axios.get(
      `/tags`,{
        params,
    ...options}
    );
  }


export const getReadTagsQueryKey = (params?: ReadTagsParams,) => [`/tags`, ...(params ? [params]: [])];

    
export type ReadTagsQueryResult = NonNullable<AsyncReturnType<typeof readTags>>
export type ReadTagsQueryError = AxiosError<HTTPValidationError>

export const useReadTags = <TData = AsyncReturnType<typeof readTags>, TError = AxiosError<HTTPValidationError>>(
 params?: ReadTagsParams, options?: { query?:UseQueryOptions<AsyncReturnType<typeof readTags>, TError, TData>, axios?: AxiosRequestConfig}

  ):  UseQueryResult<TData, TError> & { queryKey: QueryKey } => {

  const {query: queryOptions, axios: axiosOptions} = options || {}

  const queryKey = queryOptions?.queryKey ?? getReadTagsQueryKey(params);

  

  const queryFn: QueryFunction<AsyncReturnType<typeof readTags>> = () => readTags(params, axiosOptions);

  const query = useQuery<AsyncReturnType<typeof readTags>, TError, TData>(queryKey, queryFn, queryOptions)

  return {
    queryKey,
    ...query
  }
}


/**
 * @summary Read Pocket Articles
 */
export const readPocketArticles = (
    params?: ReadPocketArticlesParams, options?: AxiosRequestConfig
 ): Promise<AxiosResponse<PocketArticleRead[]>> => {
    return axios.get(
      `/pocket/articles`,{
        params,
    ...options}
    );
  }


export const getReadPocketArticlesQueryKey = (params?: ReadPocketArticlesParams,) => [`/pocket/articles`, ...(params ? [params]: [])];

    
export type ReadPocketArticlesQueryResult = NonNullable<AsyncReturnType<typeof readPocketArticles>>
export type ReadPocketArticlesQueryError = AxiosError<HTTPValidationError>

export const useReadPocketArticles = <TData = AsyncReturnType<typeof readPocketArticles>, TError = AxiosError<HTTPValidationError>>(
 params?: ReadPocketArticlesParams, options?: { query?:UseQueryOptions<AsyncReturnType<typeof readPocketArticles>, TError, TData>, axios?: AxiosRequestConfig}

  ):  UseQueryResult<TData, TError> & { queryKey: QueryKey } => {

  const {query: queryOptions, axios: axiosOptions} = options || {}

  const queryKey = queryOptions?.queryKey ?? getReadPocketArticlesQueryKey(params);

  

  const queryFn: QueryFunction<AsyncReturnType<typeof readPocketArticles>> = () => readPocketArticles(params, axiosOptions);

  const query = useQuery<AsyncReturnType<typeof readPocketArticles>, TError, TData>(queryKey, queryFn, queryOptions)

  return {
    queryKey,
    ...query
  }
}


/**
 * @summary Read Spotify History
 */
export const readSpotifyHistory = (
    params?: ReadSpotifyHistoryParams, options?: AxiosRequestConfig
 ): Promise<AxiosResponse<SpotifyTrackHistoryRead[]>> => {
    return axios.get(
      `/spotify/history`,{
        params,
    ...options}
    );
  }


export const getReadSpotifyHistoryQueryKey = (params?: ReadSpotifyHistoryParams,) => [`/spotify/history`, ...(params ? [params]: [])];

    
export type ReadSpotifyHistoryQueryResult = NonNullable<AsyncReturnType<typeof readSpotifyHistory>>
export type ReadSpotifyHistoryQueryError = AxiosError<HTTPValidationError>

export const useReadSpotifyHistory = <TData = AsyncReturnType<typeof readSpotifyHistory>, TError = AxiosError<HTTPValidationError>>(
 params?: ReadSpotifyHistoryParams, options?: { query?:UseQueryOptions<AsyncReturnType<typeof readSpotifyHistory>, TError, TData>, axios?: AxiosRequestConfig}

  ):  UseQueryResult<TData, TError> & { queryKey: QueryKey } => {

  const {query: queryOptions, axios: axiosOptions} = options || {}

  const queryKey = queryOptions?.queryKey ?? getReadSpotifyHistoryQueryKey(params);

  

  const queryFn: QueryFunction<AsyncReturnType<typeof readSpotifyHistory>> = () => readSpotifyHistory(params, axiosOptions);

  const query = useQuery<AsyncReturnType<typeof readSpotifyHistory>, TError, TData>(queryKey, queryFn, queryOptions)

  return {
    queryKey,
    ...query
  }
}


/**
 * @summary Joplin Sync
 */
export const joplinSync = (
     options?: AxiosRequestConfig
 ): Promise<AxiosResponse<unknown>> => {
    return axios.post(
      `/joplin/sync`,undefined,options
    );
  }



    export type JoplinSyncMutationResult = NonNullable<AsyncReturnType<typeof joplinSync>>
    
    export type JoplinSyncMutationError = AxiosError<unknown>

    export const useJoplinSync = <TError = AxiosError<unknown>,
    TVariables = void,
    TContext = unknown>(options?: { mutation?:UseMutationOptions<AsyncReturnType<typeof joplinSync>, TError,TVariables, TContext>, axios?: AxiosRequestConfig}
) => {
      const {mutation: mutationOptions, axios: axiosOptions} = options || {}

      


      const mutationFn: MutationFunction<AsyncReturnType<typeof joplinSync>, TVariables> = () => {
          ;

          return  joplinSync(axiosOptions)
        }

      return useMutation<AsyncReturnType<typeof joplinSync>, TError, TVariables, TContext>(mutationFn, mutationOptions)
    }
    
/**
 * @summary Joplin Get Note Id
 */
export const joplinGetNoteId = (
    dt: string, options?: AxiosRequestConfig
 ): Promise<AxiosResponse<string>> => {
    return axios.get(
      `/joplin/get_note_id/${dt}`,options
    );
  }


export const getJoplinGetNoteIdQueryKey = (dt: string,) => [`/joplin/get_note_id/${dt}`];

    
export type JoplinGetNoteIdQueryResult = NonNullable<AsyncReturnType<typeof joplinGetNoteId>>
export type JoplinGetNoteIdQueryError = AxiosError<HTTPValidationError>

export const useJoplinGetNoteId = <TData = AsyncReturnType<typeof joplinGetNoteId>, TError = AxiosError<HTTPValidationError>>(
 dt: string, options?: { query?:UseQueryOptions<AsyncReturnType<typeof joplinGetNoteId>, TError, TData>, axios?: AxiosRequestConfig}

  ):  UseQueryResult<TData, TError> & { queryKey: QueryKey } => {

  const {query: queryOptions, axios: axiosOptions} = options || {}

  const queryKey = queryOptions?.queryKey ?? getJoplinGetNoteIdQueryKey(dt);

  

  const queryFn: QueryFunction<AsyncReturnType<typeof joplinGetNoteId>> = () => joplinGetNoteId(dt, axiosOptions);

  const query = useQuery<AsyncReturnType<typeof joplinGetNoteId>, TError, TData>(queryKey, queryFn, {enabled: !!(dt), ...queryOptions})

  return {
    queryKey,
    ...query
  }
}


/**
 * @summary Google Photos Thumbnails Url
 */
export const googlePhotosThumbnailUrls = (
    dt: string, options?: AxiosRequestConfig
 ): Promise<AxiosResponse<GooglePhotosThumbnail[]>> => {
    return axios.get(
      `/googlephotos/thumbnails/${dt}`,options
    );
  }


export const getGooglePhotosThumbnailUrlsQueryKey = (dt: string,) => [`/googlephotos/thumbnails/${dt}`];

    
export type GooglePhotosThumbnailUrlsQueryResult = NonNullable<AsyncReturnType<typeof googlePhotosThumbnailUrls>>
export type GooglePhotosThumbnailUrlsQueryError = AxiosError<HTTPValidationError>

export const useGooglePhotosThumbnailUrls = <TData = AsyncReturnType<typeof googlePhotosThumbnailUrls>, TError = AxiosError<HTTPValidationError>>(
 dt: string, options?: { query?:UseQueryOptions<AsyncReturnType<typeof googlePhotosThumbnailUrls>, TError, TData>, axios?: AxiosRequestConfig}

  ):  UseQueryResult<TData, TError> & { queryKey: QueryKey } => {

  const {query: queryOptions, axios: axiosOptions} = options || {}

  const queryKey = queryOptions?.queryKey ?? getGooglePhotosThumbnailUrlsQueryKey(dt);

  

  const queryFn: QueryFunction<AsyncReturnType<typeof googlePhotosThumbnailUrls>> = () => googlePhotosThumbnailUrls(dt, axiosOptions);

  const query = useQuery<AsyncReturnType<typeof googlePhotosThumbnailUrls>, TError, TData>(queryKey, queryFn, {enabled: !!(dt), ...queryOptions})

  return {
    queryKey,
    ...query
  }
}


/**
 * @summary Google Photos Add To Joplin
 */
export const googlePhotosAddToJoplin = (
    noteId: string,
    googlePhotosThumbnail: GooglePhotosThumbnail[], options?: AxiosRequestConfig
 ): Promise<AxiosResponse<unknown>> => {
    return axios.post(
      `/googlephotos/add_to_joplin/${noteId}`,
      googlePhotosThumbnail,options
    );
  }



    export type GooglePhotosAddToJoplinMutationResult = NonNullable<AsyncReturnType<typeof googlePhotosAddToJoplin>>
    export type GooglePhotosAddToJoplinMutationBody = GooglePhotosThumbnail[]
    export type GooglePhotosAddToJoplinMutationError = AxiosError<HTTPValidationError>

    export const useGooglePhotosAddToJoplin = <TError = AxiosError<HTTPValidationError>,
    
    TContext = unknown>(options?: { mutation?:UseMutationOptions<AsyncReturnType<typeof googlePhotosAddToJoplin>, TError,{noteId: string;data: GooglePhotosThumbnail[]}, TContext>, axios?: AxiosRequestConfig}
) => {
      const {mutation: mutationOptions, axios: axiosOptions} = options || {}

      


      const mutationFn: MutationFunction<AsyncReturnType<typeof googlePhotosAddToJoplin>, {noteId: string;data: GooglePhotosThumbnail[]}> = (props) => {
          const {noteId,data} = props || {};

          return  googlePhotosAddToJoplin(noteId,data,axiosOptions)
        }

      return useMutation<AsyncReturnType<typeof googlePhotosAddToJoplin>, TError, {noteId: string;data: GooglePhotosThumbnail[]}, TContext>(mutationFn, mutationOptions)
    }
    
/**
 * @summary Send Api Json
 */
export const sendApiJsonGenerateOpenapiJsonGet = (
     options?: AxiosRequestConfig
 ): Promise<AxiosResponse<unknown>> => {
    return axios.get(
      `/generate_openapi_json`,options
    );
  }


export const getSendApiJsonGenerateOpenapiJsonGetQueryKey = () => [`/generate_openapi_json`];

    
export type SendApiJsonGenerateOpenapiJsonGetQueryResult = NonNullable<AsyncReturnType<typeof sendApiJsonGenerateOpenapiJsonGet>>
export type SendApiJsonGenerateOpenapiJsonGetQueryError = AxiosError<unknown>

export const useSendApiJsonGenerateOpenapiJsonGet = <TData = AsyncReturnType<typeof sendApiJsonGenerateOpenapiJsonGet>, TError = AxiosError<unknown>>(
  options?: { query?:UseQueryOptions<AsyncReturnType<typeof sendApiJsonGenerateOpenapiJsonGet>, TError, TData>, axios?: AxiosRequestConfig}

  ):  UseQueryResult<TData, TError> & { queryKey: QueryKey } => {

  const {query: queryOptions, axios: axiosOptions} = options || {}

  const queryKey = queryOptions?.queryKey ?? getSendApiJsonGenerateOpenapiJsonGetQueryKey();

  

  const queryFn: QueryFunction<AsyncReturnType<typeof sendApiJsonGenerateOpenapiJsonGet>> = () => sendApiJsonGenerateOpenapiJsonGet(axiosOptions);

  const query = useQuery<AsyncReturnType<typeof sendApiJsonGenerateOpenapiJsonGet>, TError, TData>(queryKey, queryFn, queryOptions)

  return {
    queryKey,
    ...query
  }
}

