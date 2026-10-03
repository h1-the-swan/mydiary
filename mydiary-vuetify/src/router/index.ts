// Composables
import { createRouter, createWebHistory } from 'vue-router'

const routes = [
    {
        path: '/',
        component: () => import('@/layouts/default/Default.vue'),
        children: [
            {
                path: '',
                name: 'Home',
                component: () => import('@/views/Home.vue'),
            },
            {
                path: '/day',
                name: 'MyDiaryDay',
                component: () => import('@/views/MyDiaryDay.vue'),
            },
            {
                path: '/performsongs',
                name: 'performSongs',
                component: () => import('@/views/PerformSongs.vue'),
            },
            {
                path: '/performsongs/new',
                name: 'new performSong',
                component: () => import('@/views/PerformSongNew.vue'),
            },
            {
                path: '/performsongs/:id',
                name: 'performSong',
                component: () => import('@/views/PerformSongs.vue'),
                props: true,
            },
            {
                path: '/performsongs/:id/practice',
                name: 'songPractice',
                component: () => import('@/views/SongPractice.vue'),
                props: true,
            },
            {
                path: '/tags',
                name: 'tags',
                component: () => import('@/views/Tags.vue'),
            },
            {
                // not `:key`: Vue reserves that prop name, and <router-view>
                // would swallow it instead of passing it to the page
                path: '/tags/:tagKey',
                name: 'tag',
                component: () => import('@/views/TagDetail.vue'),
                props: true,
            },
            {
                path: '/pocket',
                name: 'pocket',
                component: () => import('@/views/Pocket.vue'),
                props: true,
            },
            {
                path: '/tz-change',
                name: 'timeZoneChange',
                component: () => import('@/views/TimeZoneChange.vue'),
            },
            {
                path: '/spellingbee',
                name: 'spellingBee',
                component: () => import('@/views/SpellingBee.vue'),
            },
            {
                path: '/spellingbee/practice',
                name: 'spellingBeePractice',
                component: () => import('@/views/SpellingBeePractice.vue'),
            },
        ],
    },
]

const router = createRouter({
    history: createWebHistory(process.env.BASE_URL),
    routes,
    scrollBehavior(to, from, savedPosition) {
        if (to.hash) {
            return {
                el: to.hash,
                behavior: 'smooth',
            }
        }
    },
})

export default router
