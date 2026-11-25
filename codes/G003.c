#include<stdio.h>
int main()
{
    int i,j,z;
    for(i=1;i<=4;i++)
    {
        for(j=1;j<=4-i;j++)
            printf(" ");
        for(j=1;j<=2*i-1;j++){
            z='A';
            printf("%d",z++);
        }
        printf("\n");
    }
    return 0;
}
