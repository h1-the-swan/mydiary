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
                // route level code-splitting
                // this generates a separate chunk (about.[hash].js) for this route
                // which is lazy-loaded when the route is visited.
                component: () =>
                    import(/* webpackChunkName: "home" */ '@/views/Home.vue'),
            },
            {
                path: '/test',
                name: 'Test',
                component: () =>
                    import(/* webpackChunkName: "test" */ '@/views/Test.vue'),
            },
            {
                path: '/testday',
                name: 'TestDay',
                component: () =>
                    import(
                        /* webpackChunkName: "test" */ '@/views/TestDay.vue'
                    ),
            },
            {
                path: '/day',
                name: 'MyDiaryDay',
                component: () =>
                    import(
                        /* webpackChunkName: "test" */ '@/views/MyDiaryDay.vue'
                    ),
            },
            {
                path: '/performsongs',
                name: 'performSongs',
                component: () =>
                    import(
                        /* webpackChunkName: "performsong" */ '@/views/PerformSongs.vue'
                    ),
            },
            {
                path: '/performsongs/new',
                name: 'new performSong',
                component: () =>
                    import(
                        /* webpackChunkName: "performsong" */ '@/views/PerformSongNew.vue'
                    ),
            },
            {
                path: '/performsongs/:id',
                name: 'performSong',
                component: () =>
                    import(
                        /* webpackChunkName: "performsong" */ '@/views/PerformSongs.vue'
                    ),
                props: true,
            },
            {
                path: '/pocket',
                name: 'pocket',
                component: () =>
                    import(
                        /* webpackChunkName: "pocket" */ '@/views/Pocket.vue'
                    ),
                props: true,
            },
            {
                path: '/tz-change',
                name: 'timeZoneChange',
                component: () =>
                    import(
                        /* webpackChunkName: "pocket" */ '@/views/TimeZoneChange.vue'
                    ),
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
