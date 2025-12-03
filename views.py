from rest_framework import viewsets,filters
from .models import *
from .serializers import *
from rest_framework import permissions
from rest_framework.response import Response
from django.db.models import Prefetch
from rest_framework.exceptions import PermissionDenied
from rest_framework.parsers import MultiPartParser, FormParser
from .pagination import CustomPagination
from django_filters.rest_framework import DjangoFilterBackend





class UserTuzilmaViewSet(viewsets.ModelViewSet):
    serializer_class = UserTuzilmaSerializer
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def get_queryset(self):
        user = self.request.user

        if user.is_superuser or user.is_admin():
            # Adminlar va superuser barcha foydalanuvchilarni ko‘radi
            return CustomUser.objects.all().order_by('-id')
        else:
            # Foydalanuvchi faqat o‘zini ko‘radi
            return CustomUser.objects.filter(id=user.id)

    # CREATE – faqat admin/superuser
    def perform_create(self, serializer):
        user = self.request.user
        if not (user.is_superuser or user.is_admin()):
            raise PermissionDenied("Faqat admin foydalanuvchi yaratishi mumkin.")
        serializer.save()

    # UPDATE – faqat admin/superuser
    def perform_update(self, serializer):
        user = self.request.user
        if not (user.is_superuser or user.is_admin()):
            raise PermissionDenied("Faqat admin foydalanuvchi o‘zgartirishi mumkin.")
        serializer.save()

    # DELETE – faqat admin/superuser
    def perform_destroy(self, instance):
        user = self.request.user
        if not (user.is_superuser or user.is_admin()):
            raise PermissionDenied("Faqat admin foydalanuvchi o‘chirishi mumkin.")
        instance.delete()




class TuzilmaNomiViewSet(viewsets.ModelViewSet):
    queryset = TarkibiyTuzilma.objects.filter(status=True)
    serializer_class = TuzilmaSerializers

    def get_queryset(self):
        return TarkibiyTuzilma.objects.filter(status=True)


class ArizaYuborishViewSet(viewsets.ModelViewSet):
    serializer_class = ArizaYuborishSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter, DjangoFilterBackend]
    search_fields = ['status', 'tuzilma__tuzilma_nomi', 'kim_tomonidan__tuzilma_nomi', 'created_by__username']
    ordering_fields = ['id', 'sana', 'status']
    filterset_fields = ['status', 'is_approved', 'tuzilma__tuzilma_nomi', 'kim_tomonidan__tuzilma_nomi']
    pagination_class = CustomPagination

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser:
            return ArizaYuborish.objects.all()
        return ArizaYuborish.objects.filter(created_by=user)

    def perform_create(self, serializer):
        user = self.request.user
        serializer.save(
            status="jarayonda",
            is_approved=user.is_superuser
        )





            
   
class KelganArizalarViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = ArizaYuborishWithKelganSerializer
    permission_classes = [permissions.IsAuthenticated]
    search_fields = ['status', 'tuzilma__tuzilma_nomi', 'kim_tomonidan__tuzilma_nomi', 'created_by__username']
    ordering_fields = ['id', 'sana', 'status']
    filterset_fields = ['status', 'is_approved', 'tuzilma__tuzilma_nomi', 'kim_tomonidan__tuzilma_nomi']
    pagination_class = CustomPagination

    def get_queryset(self):
        user = self.request.user

        if user.is_superuser:
            return ArizaYuborish.objects.prefetch_related(
                Prefetch('kelganlar', queryset=KelganArizalar.objects.all())
            )

        # Foydalanuvchi tarkibiy tuzilmami yoki bekat rahbarimi
        if user.tarkibiy_tuzilma:
            return ArizaYuborish.objects.filter(
                tuzilma=user.tarkibiy_tuzilma
            ).prefetch_related(
                Prefetch('kelganlar', queryset=KelganArizalar.objects.all())
            )

        elif user.bekat_nomi:
            # Bekat nomi bilan tuzilma mapping
            tuzilma = TarkibiyTuzilma.objects.filter(tuzilma_nomi=user.bekat_nomi).first()
            if tuzilma:
                return ArizaYuborish.objects.filter(
                    tuzilma=tuzilma
                ).prefetch_related(
                    Prefetch('kelganlar', queryset=KelganArizalar.objects.all())
                )
        return ArizaYuborish.objects.none()



class KelganArizalarCreateViewSet(viewsets.ModelViewSet):
    serializer_class = KelganArizalarSerializer
    permission_classes = [permissions.IsAuthenticated]
    search_fields = ['status', 'tuzilma__tuzilma_nomi', 'kim_tomonidan__tuzilma_nomi', 'created_by__username']
    ordering_fields = ['id', 'sana', 'status']
    filterset_fields = ['status', 'is_approved', 'tuzilma__tuzilma_nomi', 'kim_tomonidan__tuzilma_nomi']
    pagination_class = CustomPagination

    def get_queryset(self):
        user = self.request.user
        qs = KelganArizalar.objects.all()
        
        if user.is_superuser:
            return qs
        elif user.tarkibiy_tuzilma:
            return qs.filter(ariza__tuzilma=user.tarkibiy_tuzilma)
        elif user.bekat_nomi:
            tuzilma = TarkibiyTuzilma.objects.filter(tuzilma_nomi=user.bekat_nomi.bekat_nomi).first()
            if tuzilma:
                return qs.filter(ariza__tuzilma=tuzilma)
        return qs.none()

    def get_serializer(self, *args, **kwargs):
        serializer_class = self.get_serializer_class()
        kwargs['context'] = self.get_serializer_context()
        serializer = serializer_class(*args, **kwargs)

        # Agar serializer list bo'lsa, fields ga kira olmaymiz
        if not getattr(serializer, 'fields', None):
            return serializer

        # Arizalarni tanlash uchun faqat o'ziga kelgan va jarayonda bo'lgan arizalarni ko'rsatish
        user = self.request.user
        ariza_qs = ArizaYuborish.objects.filter(status="jarayonda")
        if not user.is_superuser:
            if user.tarkibiy_tuzilma:
                ariza_qs = ariza_qs.filter(tuzilma=user.tarkibiy_tuzilma)
            elif user.bekat_nomi:
                tuzilma = TarkibiyTuzilma.objects.filter(tuzilma_nomi=user.bekat_nomi.bekat_nomi).first()
                if tuzilma:
                    ariza_qs = ariza_qs.filter(tuzilma=tuzilma)
                else:
                    ariza_qs = ArizaYuborish.objects.none()

        serializer.fields['ariza'].queryset = ariza_qs
        return serializer


    def perform_create(self, serializer):
        user = self.request.user
        kelgan = serializer.save(
            created_by=user,
            is_approved=user.is_superuser
        )
        # Javob qo‘shilganda asosiy arizani statusini "bajarildi" ga o‘zgartirish
        ariza = kelgan.ariza
        ariza.status = "bajarildi"
        ariza.save()





            
class PPRTuriViewSet(viewsets.ModelViewSet):
    queryset = PPRTuri.objects.all()
    serializer_class = PPRTuriSerializer


class ObyektNomiViewSet(viewsets.ModelViewSet):
    queryset = ObyektNomi.objects.all()
    serializer_class = ObyektNomiSerializer
    pagination_class = CustomPagination


class PPRJadvalViewSet(viewsets.ModelViewSet):
    queryset = PPRJadval.objects.all()
    serializer_class = PPRJadvalSerializer
    pagination_class = CustomPagination


class HujjatlarViewSet(viewsets.ModelViewSet):
    queryset = Hujjatlar.objects.all()
    serializer_class = HujjatlarSerializer
    pagination_class = CustomPagination


class NotificationsViewSet(viewsets.ModelViewSet):
    queryset = Notifications.objects.all()
    serializer_class = NotificationsSerializer
