pipeline {
  agent any
  environment { IMAGE = "${env.DOCKERHUB_USERNAME}/roadwise:${env.BUILD_NUMBER}" }
  stages {
    stage('Checkout') { steps { checkout scm } }
    stage('Build image') { steps { sh 'docker build -t "$IMAGE" .' } }
    stage('Publish image') {
      when { branch 'main' }
      steps {
        withCredentials([usernamePassword(credentialsId: 'dockerhub', usernameVariable: 'DOCKER_USER', passwordVariable: 'DOCKER_TOKEN')]) {
          sh 'echo "$DOCKER_TOKEN" | docker login -u "$DOCKER_USER" --password-stdin'
          sh 'docker push "$IMAGE"'
        }
      }
    }
    stage('Deploy') {
      when { branch 'main' }
      steps {
        sshagent(credentials: ['deploy-ssh']) {
          sh 'ssh -o StrictHostKeyChecking=accept-new "$DEPLOY_USER@$DEPLOY_HOST" "cd /opt/roadwise && IMAGE=$IMAGE docker compose pull web && IMAGE=$IMAGE docker compose up -d web"'
        }
      }
    }
  }
  post { always { sh 'docker image prune -f || true' } }
}
