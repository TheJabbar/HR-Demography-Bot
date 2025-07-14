@Library(['shared-library', 'pipeline-library']) _
def vault = new Vault()

// Cek panduan di wiki berikut: https://gitlab.playcourt.id/devops/devsecops-wiki
PipelineDockerEntryV2([
    // Nama project anda sesuai yang terdaftar di Playcourt. Nama sudah ditentukan di awal, mohon tidak di ubah tanpa komunikasi dengan tim Playcourt.
    projectName: 'telkom-dag-ai',

    // Nama dari service yang anda buat dan akan digunakan sebagai nama image docker.
    imageName: 'telkom-dag-ai-hcm-insight',

    // Nama cluster di mana service akan dideploy. Deployment sudah ditentukan di awal, mohon tidak di ubah tanpa komunikasi dengan tim Playcourt.
    deployment: 'bigengine',

    // Prerun Script
    // Pada bagian ini anda dapat menambahkan dan mengkonfigurasikan script untuk dijalankan sebelum melakukan test atau build service yang anda buat
    prerunAgent: 'bigengine',
    // Prerun Script
    // Pada bagian ini anda dapat menambahkan dan mengkonfigurasikan script untuk dijalankan sebelum melakukan test atau build service yang anda buat
    prerunAgent: 'Gitops',
    prerunAgentImage: 'playcourt/jenkins:nodejs18',
    prerunScript: {
        // "prerunScript" berisi groovy script yang akan dijalankan sebelum step test dan build
        // Pada bagian ini anda juga dapat membuat variable dan menggunakannya pada script yang lain

        // contoh script untuk mengambil secret dari Vault dan menyimpannya ke dalam file .env:
        useDotenv = vault.createDotenv("dag/telkom-dag-ai/${env.BRANCH_NAME}/telkom-dag-ai-hcm-insight")
    },


    // Service Test
    // Pada bagian ini anda dapat menambahkan dan mengkonfigurasikan script untuk menjalankan test pada service yang anda buat
    testAgent: 'Docker',
    testAgentImage: 'playcourt/python:3.11.0', // Untuk option ini, hanya gunakan image dari https://hub.docker.com/r/playcourt/jenkins
    runTestScript: {
        // "runTestScript" berisi groovy script untuk menjalankan test
        sh """
            apk add --no-cache wget curl git build-base python3-dev \
            libffi-dev \
            build-base \
            sqlite \
            sqlite-dev
            apk update && apk upgrade && apk add build-base && apk add openjdk17
            pip install uv
            uv pip install -r pyproject.toml --extra dev --system
        """
        useDotenv {
            sh "coverage run --source ./ -m pytest --asyncio-mode=auto -v --cov-config=pyproject.toml && coverage xml"
        }
        sh "coverage report -m"
    },

    // Build Docker Image
    // Pada bagian ini anda dapat mengkonfigurasikan script untuk membuat image dari service yang anda buat
    buildAgent: 'bigengine',
    buildDockerImageScript: { String imageTag, String envStage, String buildCommand ->
        // "buildDockerImageScript" berisi groovy script untuk melakukan build image
        // Wajib menggunakan variable buildCommand untuk menjalankan perintah docker build
        // Image yang dibuat wajib menggunakan tag dari variable imageTag

        // contoh script untuk menggunakan file .env yang dibuat pada prerunScript dan membuat image
        // useDotenv {
        //     sh "${buildCommand} -t ${imageTag} ."
        // }

        sh "${buildCommand} -t ${imageTag} ."
    },

    // Post Run Script
    // Pada bagian ini anda dapat menambahkan script untuk dijalankan setelah proses pada pipeline selesai
    postrunScript: [
        always: {
            // Pada bagian ini script akan dijalankan setiap pipeline selesai
        },

        success: {
            // Pada bagian ini script hanya akan dijalankan jika pipeline sukses
        },

        failure: {
            // Pada bagian ini script hanya akan dijalankan jika pipeline gagal
        }
    ]
])
